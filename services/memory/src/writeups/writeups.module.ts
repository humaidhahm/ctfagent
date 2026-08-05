import { Module } from '@nestjs/common';
import { SourceDocumentsService } from './source-documents.service';
import { WriteupsService } from './writeups.service';

@Module({
  providers: [WriteupsService, SourceDocumentsService],
  exports: [WriteupsService, SourceDocumentsService],
})
export class WriteupsModule {}
