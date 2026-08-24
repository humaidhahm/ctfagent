import {
  BadRequestException,
  Body,
  Controller,
  Get,
  Headers,
  HttpCode,
  HttpStatus,
  InternalServerErrorException,
  NotFoundException,
  Param,
  Post,
  Query,
  UnauthorizedException,
} from '@nestjs/common';
import { McpService } from './mcp.service';
import { WebReferenceService } from '../web/web-reference.service';
import { WriteupsService } from '../writeups/writeups.service';

const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 50;
const MAX_OFFSET = 100000;

type QueryValue = string | string[] | undefined;

@Controller('mcp')
export class McpController {
  private readonly apiToken = process.env.MEMORY_API_TOKEN?.trim() ?? '';

  constructor(
    private readonly mcp: McpService,
    private readonly writeups: WriteupsService,
    private readonly webReferences: WebReferenceService,
  ) {}

  @Get()
  health(): { status: 'ok'; service: string; protocol: string } {
    return { status: 'ok', service: 'memory', protocol: 'mcp' };
  }

  @Get('writeups')
  async listWriteups(
    @Query() query: Record<string, QueryValue>,
    @Headers('authorization') authorization?: string,
  ): Promise<unknown> {
    this.authorize(authorization);
    const limit = this.parseLimit(query.limit);
    const offset = this.parseOffset(query.offset);
    const search = {
      query: this.parseOptionalText(query.query, 'query'),
      domain: this.parseOptionalText(query.domain, 'domain'),
      difficulty: this.parseOptionalText(query.difficulty, 'difficulty'),
      limit,
      offset,
    };
    try {
      return await this.writeups.search(search);
    } catch {
      throw new InternalServerErrorException('Unable to retrieve writeups.');
    }
  }

  @Get('writeups/:id')
  async getWriteup(
    @Param('id') idValue: string,
    @Headers('authorization') authorization?: string,
  ): Promise<unknown> {
    this.authorize(authorization);
    const id = Number(idValue);
    if (!/^\d+$/.test(idValue) || !Number.isSafeInteger(id) || id < 1) {
      throw new BadRequestException('id must be a positive integer.');
    }
    try {
      const writeup = await this.writeups.getById(id);
      if (!writeup) {
        throw new NotFoundException('Writeup not found.');
      }
      return writeup;
    } catch (error: unknown) {
      if (error instanceof NotFoundException) {
        throw error;
      }
      throw new InternalServerErrorException('Unable to retrieve writeup.');
    }
  }

  @Post('references')
  @HttpCode(HttpStatus.OK)
  async createReference(
    @Body() body: unknown,
    @Headers('authorization') authorization?: string,
  ): Promise<unknown> {
    this.authorize(authorization);
    if (!this.isRecord(body) || typeof body.url !== 'string' || body.url.length === 0 || body.url.length > 2048) {
      throw new BadRequestException('url must be a non-empty string no longer than 2048 characters.');
    }
    try {
      return await this.webReferences.fetchReference(body.url);
    } catch {
      throw new BadRequestException('Unable to fetch the requested web reference.');
    }
  }

  @Post()
  @HttpCode(HttpStatus.OK)
  async jsonRpc(
    @Body() body: unknown,
    @Headers('authorization') authorization?: string,
  ): Promise<unknown> {
    this.authorize(authorization);
    try {
      return await this.mcp.handleRpc(body);
    } catch {
      return {
        jsonrpc: '2.0',
        id: null,
        error: { code: -32603, message: 'Internal error.' },
      };
    }
  }

  private parseLimit(value: QueryValue): number {
    if (value === undefined) {
      return DEFAULT_LIMIT;
    }
    if (Array.isArray(value) || !/^\d+$/.test(value)) {
      throw new BadRequestException(`limit must be an integer between 1 and ${MAX_LIMIT}.`);
    }
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed) || parsed < 1 || parsed > MAX_LIMIT) {
      throw new BadRequestException(`limit must be an integer between 1 and ${MAX_LIMIT}.`);
    }
    return parsed;
  }

  private parseOffset(value: QueryValue): number {
    if (value === undefined) {
      return 0;
    }
    if (Array.isArray(value) || !/^\d+$/.test(value)) {
      throw new BadRequestException(`offset must be an integer between 0 and ${MAX_OFFSET}.`);
    }
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed) || parsed < 0 || parsed > MAX_OFFSET) {
      throw new BadRequestException(`offset must be an integer between 0 and ${MAX_OFFSET}.`);
    }
    return parsed;
  }

  private parseOptionalText(value: QueryValue, name: string): string | undefined {
    if (value === undefined) {
      return undefined;
    }
    if (Array.isArray(value) || value.length > 2000) {
      throw new BadRequestException(`${name} must be a string no longer than 2000 characters.`);
    }
    return value;
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
  }

  private authorize(authorization?: string): void {
    if (!this.apiToken) {
      return;
    }
    const expected = `Bearer ${this.apiToken}`;
    if (authorization !== expected) {
      throw new UnauthorizedException('A valid bearer token is required.');
    }
  }
}
