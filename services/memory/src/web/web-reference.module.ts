import { Module } from '@nestjs/common';
import { DatabaseModule } from '../database/database.module';
import { WebReferenceService } from './web-reference.service';

@Module({
  imports: [DatabaseModule],
  providers: [WebReferenceService],
  exports: [WebReferenceService],
})
export class WebReferenceModule {}
