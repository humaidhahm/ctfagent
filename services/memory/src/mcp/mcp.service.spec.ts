import { McpService } from './mcp.service';
import { SourceDocumentsService } from '../writeups/source-documents.service';
import { WriteupsService } from '../writeups/writeups.service';
import { WebReferenceService } from '../web/web-reference.service';

function createService(): {
  service: McpService;
  writeups: jest.Mocked<WriteupsService>;
  sourceDocuments: jest.Mocked<SourceDocumentsService>;
  webReferences: jest.Mocked<WebReferenceService>;
} {
  const writeups = {
    search: jest.fn(),
    getById: jest.fn(),
    getByChallengeName: jest.fn(),
    listDomains: jest.fn(),
  } as unknown as jest.Mocked<WriteupsService>;
  const sourceDocuments = {
    search: jest.fn(),
    getById: jest.fn(),
  } as unknown as jest.Mocked<SourceDocumentsService>;
  const webReferences = {
    fetchReference: jest.fn(),
  } as unknown as jest.Mocked<WebReferenceService>;
  return {
    service: new McpService(writeups, sourceDocuments, webReferences),
    writeups,
    sourceDocuments,
    webReferences,
  };
}

describe('McpService', () => {
  it('returns MCP initialization metadata', async () => {
    const { service } = createService();

    await expect(service.handleRpc({ jsonrpc: '2.0', id: 7, method: 'initialize' })).resolves.toEqual({
      jsonrpc: '2.0',
      id: 7,
      result: {
        protocolVersion: '2024-11-05',
        capabilities: { tools: {} },
        serverInfo: { name: 'memory', version: '0.1.0' },
      },
    });
  });

  it('delegates writeup search and serializes a bounded tool result', async () => {
    const { service, writeups } = createService();
    const page = { items: [{ id: 1, challengeName: 'Flag Leak' }], total: 1, limit: 5, offset: 0 };
    writeups.search.mockResolvedValue(page as never);

    const response = await service.handleRpc({
      jsonrpc: '2.0',
      id: 'search',
      method: 'tools/call',
      params: { name: 'search_writeups', arguments: { query: 'flag', limit: 5 } },
    });

    expect(writeups.search).toHaveBeenCalledWith({
      query: 'flag',
      domain: undefined,
      difficulty: undefined,
      limit: 5,
      offset: 0,
    });
    expect(response).toEqual({
      jsonrpc: '2.0',
      id: 'search',
      result: { content: [{ type: 'text', text: JSON.stringify(page) }] },
    });
  });

  it('returns a protocol error for unknown tools', async () => {
    const { service } = createService();

    await expect(service.handleRpc({
      jsonrpc: '2.0',
      id: 1,
      method: 'tools/call',
      params: { name: 'no_such_tool', arguments: {} },
    })).resolves.toEqual({
      jsonrpc: '2.0',
      id: 1,
      error: { code: -32602, message: 'Unknown tool: no_such_tool.' },
    });
  });
});
