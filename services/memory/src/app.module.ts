import { Module } from '@nestjs/common';
import { DatabaseModule } from './database/database.module';
import { McpModule } from './mcp/mcp.module';
import { WebReferenceModule } from './web/web-reference.module';
import { WriteupsModule } from './writeups/writeups.module';

@Module({
  imports: [DatabaseModule, WriteupsModule, WebReferenceModule, McpModule],
})
export class AppModule {}
