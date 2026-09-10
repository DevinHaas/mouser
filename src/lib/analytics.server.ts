import { logs } from '@opentelemetry/api-logs'
import { OTLPLogExporter } from '@opentelemetry/exporter-logs-otlp-http'
import { resourceFromAttributes } from '@opentelemetry/resources'
import { BatchLogRecordProcessor } from '@opentelemetry/sdk-logs'
import { NodeSDK } from '@opentelemetry/sdk-node'
import { PostHog } from 'posthog-node'

type Properties = Record<string, string | number | boolean>

const key = import.meta.env.PUBLIC_POSTHOG_KEY
const host = import.meta.env.PUBLIC_POSTHOG_HOST ?? 'https://eu.i.posthog.com'

if (key) {
  new NodeSDK({
    resource: resourceFromAttributes({ 'service.name': 'mouser' }),
    logRecordProcessor: new BatchLogRecordProcessor(
      new OTLPLogExporter({
        url: `${host.replace(/\/$/, '')}/i/v1/logs`,
        headers: { Authorization: `Bearer ${key}` },
      }),
    ),
  }).start()
}

const logger = logs.getLogger('mouser')
const posthog = key
  ? new PostHog(key, {
      host,
      flushAt: 1,
      enableExceptionAutocapture: true,
    })
  : null

export function captureServerError(error: unknown, properties: Properties) {
  const exception = error instanceof Error ? error : new Error(String(error))
  console.error(`[mouser] ${properties.operation ?? 'server_error'}`, exception, properties)
  logger.emit({
    severityText: 'ERROR',
    body: exception.message,
    attributes: {
      ...properties,
      'exception.type': exception.name,
      'exception.message': exception.message,
      'exception.stacktrace': exception.stack ?? '',
    },
  })
  posthog?.captureException(exception, undefined, properties)
}
