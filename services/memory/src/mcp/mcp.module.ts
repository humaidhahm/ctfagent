import { Module } from '@nestjs/common';
import { WriteupsModule } from '../writeups/writeups.module';
import { WebReferenceModule } from '../web/web-reference.module';
import { McpController } from './mcp.controller';
import { McpService } from './mcp.service';

@Module({
  imports: [WriteupsModule, WebReferenceModule],
  controllers: [McpController],
  providers: [McpService],
  exports: [McpService],
})
export class McpModule {}
