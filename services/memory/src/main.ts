import 'dotenv/config';
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

function readCorsOrigins(): string[] {
  return (process.env.MEMORY_CORS_ORIGINS ?? '')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);
}

function requireConfiguredAuth(): void {
  const required = (process.env.MEMORY_REQUIRE_AUTH ?? '').toLowerCase() === 'true';
  const token = process.env.MEMORY_API_TOKEN?.trim();
  if (required && !token) {
    throw new Error('MEMORY_REQUIRE_AUTH=true requires MEMORY_API_TOKEN to be configured.');
  }
}

async function bootstrap(): Promise<void> {
  requireConfiguredAuth();
  const app = await NestFactory.create(AppModule);
  const corsOrigins = readCorsOrigins();
  if (corsOrigins.length > 0) {
    app.enableCors({ origin: corsOrigins });
  }
  const port = Number.parseInt(process.env.PORT ?? '3000', 10);
  await app.listen(port, '0.0.0.0');
}

void bootstrap().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
