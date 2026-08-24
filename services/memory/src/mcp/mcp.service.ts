import { Injectable } from '@nestjs/common';
import { SourceDocumentsService } from '../writeups/source-documents.service';
import { WriteupsService } from '../writeups/writeups.service';
import { WebReferenceService, WebReferenceValidationError } from '../web/web-reference.service';

const MAX_LIMIT = 50;
const DEFAULT_LIMIT = 20;
const MAX_OFFSET = 100000;
const MAX_TOOL_TEXT_LENGTH = 128 * 1024;
const PROTOCOL_VERSION = '2024-11-05';

type JsonRpcId = string | number | null;
type JsonObject = Record<string, unknown>;

export interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: JsonRpcId;
  result?: JsonObject;
  error?: {
    code: number;
    message: string;
  };
}

interface ToolDefinition {
  name: string;
  description: string;
  inputSchema: JsonObject;
}

class InvalidParamsError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'InvalidParamsError';
  }
}

@Injectable()
export class McpService {
  private readonly tools: ToolDefinition[] = [
    {
      name: 'search_writeups',
      description: 'Search picoCTF writeups by text, domain, or difficulty.',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'Text to search for.' },
          domain: { type: 'string' },
          difficulty: { type: 'string' },
          limit: { type: 'integer', minimum: 1, maximum: MAX_LIMIT },
          offset: { type: 'integer', minimum: 0, maximum: MAX_OFFSET },
        },
        additionalProperties: false,
      },
    },
    {
      name: 'get_writeup',
      description: 'Get one picoCTF writeup by numeric id.',
      inputSchema: {
        type: 'object',
        properties: { id: { type: 'integer', minimum: 1 } },
        required: ['id'],
        additionalProperties: false,
      },
    },
    {
      name: 'list_domains',
      description: 'List writeup domains and their counts.',
      inputSchema: { type: 'object', properties: {}, additionalProperties: false },
    },
    {
      name: 'search_source_documents',
      description: 'Search ingested repository source documents.',
      inputSchema: {
        type: 'object',
        properties: {
          query: { type: 'string' },
          limit: { type: 'integer', minimum: 1, maximum: MAX_LIMIT },
          offset: { type: 'integer', minimum: 0, maximum: MAX_OFFSET },
        },
        additionalProperties: false,
      },
    },
    {
      name: 'get_source_document',
      description: 'Get one source document by numeric id.',
      inputSchema: {
        type: 'object',
        properties: { id: { type: 'integer', minimum: 1 } },
        required: ['id'],
        additionalProperties: false,
      },
    },
    {
      name: 'fetch_web_reference',
      description: 'Fetch a bounded, allow-listed web reference with caching.',
      inputSchema: {
        type: 'object',
        properties: { url: { type: 'string', maxLength: 2048 } },
        required: ['url'],
        additionalProperties: false,
      },
    },
  ];

  constructor(
    private readonly writeups: WriteupsService,
    private readonly sourceDocuments: SourceDocumentsService,
    private readonly webReferences: WebReferenceService,
  ) {}

  async handleRpc(rawBody: unknown): Promise<JsonRpcResponse> {
    let body: unknown = rawBody;
    if (typeof rawBody === 'string') {
      try {
        body = JSON.parse(rawBody) as unknown;
      } catch {
        return this.errorResponse(null, -32700, 'Parse error.');
      }
    }
    if (!this.isRecord(body) || body.jsonrpc !== '2.0' || typeof body.method !== 'string') {
      return this.errorResponse(null, -32600, 'Invalid Request.');
    }

    const id = this.readId(body.id);
    if (body.id !== undefined && id === undefined) {
      return this.errorResponse(null, -32600, 'Invalid Request.');
    }

    try {
      switch (body.method) {
        case 'initialize':
          return { jsonrpc: '2.0', id: id ?? null, result: this.initializeResult() };
        case 'tools/list':
          return { jsonrpc: '2.0', id: id ?? null, result: { tools: this.tools } };
        case 'tools/call':
          return {
            jsonrpc: '2.0',
            id: id ?? null,
            result: await this.callTool(body.params),
          };
        default:
          return this.errorResponse(id ?? null, -32601, 'Method not found.');
      }
    } catch (error: unknown) {
      if (error instanceof InvalidParamsError) {
        return this.errorResponse(id ?? null, -32602, error.message);
      }
      return this.errorResponse(id ?? null, -32603, 'Internal error.');
    }
  }

  private initializeResult(): JsonObject {
    return {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: { tools: {} },
      serverInfo: { name: 'memory', version: '0.1.0' },
    };
  }

  private async callTool(rawParams: unknown): Promise<JsonObject> {
    if (
      !this.isRecord(rawParams)
      || typeof rawParams.name !== 'string'
      || rawParams.name.length === 0
      || rawParams.name.length > 100
    ) {
      throw new InvalidParamsError('tools/call requires a tool name no longer than 100 characters.');
    }
    const rawArguments = rawParams.arguments ?? {};
    if (!this.isRecord(rawArguments)) {
      throw new InvalidParamsError('Tool arguments must be a JSON object.');
    }

    let value: unknown;
    switch (rawParams.name) {
      case 'search_writeups':
        value = await this.searchWriteups(rawArguments);
        break;
      case 'get_writeup':
        value = await this.getWriteup(rawArguments);
        break;
      case 'list_domains':
        this.rejectUnknownArguments(rawArguments);
        value = await this.writeups.listDomains();
        break;
      case 'search_source_documents':
        value = await this.searchSourceDocuments(rawArguments);
        break;
      case 'get_source_document':
        value = await this.getSourceDocument(rawArguments);
        break;
      case 'fetch_web_reference':
        value = await this.fetchWebReference(rawArguments);
        break;
      default:
        throw new InvalidParamsError(`Unknown tool: ${rawParams.name}.`);
    }

    const toolResult: JsonObject = {
      content: [{ type: 'text', text: this.serializeBounded(value) }],
    };
    if (this.isRecord(value) && typeof value.error === 'string') {
      toolResult.isError = true;
    }
    return toolResult;
  }

  private async searchWriteups(args: JsonObject): Promise<unknown> {
    this.rejectUnknownArguments(args, ['query', 'domain', 'difficulty', 'limit', 'offset']);
    const limit = this.readLimit(args.limit);
    const offset = this.readOffset(args.offset);
    return this.writeups.search({
      query: this.readOptionalText(args.query, 'query'),
      domain: this.readOptionalText(args.domain, 'domain'),
      difficulty: this.readOptionalText(args.difficulty, 'difficulty'),
      limit,
      offset,
    });
  }

  private async getWriteup(args: JsonObject): Promise<unknown> {
    this.rejectUnknownArguments(args, ['id']);
    return this.writeups.getById(this.readIdArgument(args));
  }

  private async searchSourceDocuments(args: JsonObject): Promise<unknown> {
    this.rejectUnknownArguments(args, ['query', 'limit', 'offset']);
    const limit = this.readLimit(args.limit);
    const offset = this.readOffset(args.offset);
    return this.sourceDocuments.search({
      query: this.readOptionalText(args.query, 'query'),
      limit,
      offset,
    });
  }

  private async getSourceDocument(args: JsonObject): Promise<unknown> {
    this.rejectUnknownArguments(args, ['id']);
    return this.sourceDocuments.getById(this.readIdArgument(args));
  }

  private async fetchWebReference(args: JsonObject): Promise<unknown> {
    this.rejectUnknownArguments(args, ['url']);
    const url = args.url;
    if (typeof url !== 'string' || url.length === 0 || url.length > 2048) {
      throw new InvalidParamsError('url must be a non-empty string no longer than 2048 characters.');
    }
    try {
      return await this.webReferences.fetchReference(url);
    } catch (error: unknown) {
      if (error instanceof WebReferenceValidationError) {
        throw new InvalidParamsError(error.message);
      }
      throw error;
    }
  }

  private readIdArgument(args: JsonObject): number {
    const id = args.id;
    if (typeof id !== 'number' || !Number.isSafeInteger(id) || id < 1) {
      throw new InvalidParamsError('id must be a positive integer.');
    }
    return id;
  }

  private readLimit(value: unknown): number {
    if (value === undefined) {
      return DEFAULT_LIMIT;
    }
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1 || value > MAX_LIMIT) {
      throw new InvalidParamsError(`limit must be an integer between 1 and ${MAX_LIMIT}.`);
    }
    return value;
  }

  private readOffset(value: unknown): number {
    if (value === undefined) {
      return 0;
    }
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0 || value > MAX_OFFSET) {
      throw new InvalidParamsError(`offset must be an integer between 0 and ${MAX_OFFSET}.`);
    }
    return value;
  }

  private readOptionalText(value: unknown, name: string): string | undefined {
    if (value === undefined) {
      return undefined;
    }
    if (typeof value !== 'string' || value.length > 2000) {
      throw new InvalidParamsError(`${name} must be a string no longer than 2000 characters.`);
    }
    return value;
  }

  private rejectUnknownArguments(args: JsonObject, allowed: string[] = []): void {
    for (const key of Object.keys(args)) {
      if (!allowed.includes(key)) {
        throw new InvalidParamsError('Unknown tool argument.');
      }
    }
  }

  private serializeBounded(value: unknown): string {
    let valueToSerialize = value;
    if (this.isRecord(value) && typeof value.markdown === 'string' && value.markdown.length > MAX_TOOL_TEXT_LENGTH) {
      valueToSerialize = {
        ...value,
        markdown: `${value.markdown.slice(0, MAX_TOOL_TEXT_LENGTH)}\n[truncated]`,
      };
    }
    let text: string;
    try {
      text = JSON.stringify(valueToSerialize) ?? 'null';
    } catch {
      text = 'null';
    }
    if (text.length <= MAX_TOOL_TEXT_LENGTH) {
      return text;
    }
    return `${text.slice(0, MAX_TOOL_TEXT_LENGTH)}\n[truncated]`;
  }

  private errorResponse(id: JsonRpcId, code: number, message: string): JsonRpcResponse {
    return { jsonrpc: '2.0', id, error: { code, message } };
  }

  private readId(value: unknown): JsonRpcId | undefined {
    if (value === undefined) {
      return null;
    }
    if (value === null) {
      return null;
    }
    if (typeof value === 'string' && value.length <= 200) {
      return value;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    return undefined;
  }

  private isRecord(value: unknown): value is JsonObject {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
  }
}
