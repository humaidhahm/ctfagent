import { DatabaseService } from '../database/database.service';
import { WebReferenceService } from './web-reference.service';

describe('WebReferenceService', () => {
  it('rejects localhost before opening a database cache query', async () => {
    const database = { query: jest.fn() } as unknown as DatabaseService;
    const service = new WebReferenceService(database);

    await expect(service.fetchReference('http://localhost:3000/private')).rejects.toThrow(
      'Local, private, and link-local hosts are not allowed.',
    );
    expect(database.query).not.toHaveBeenCalled();
  });

  it('rejects hosts outside the configured allow-list', async () => {
    const database = { query: jest.fn() } as unknown as DatabaseService;
    const service = new WebReferenceService(database);

    await expect(service.fetchReference('https://example.com/reference')).rejects.toThrow(
      'The URL host is not allow-listed.',
    );
    expect(database.query).not.toHaveBeenCalled();
  });
});
