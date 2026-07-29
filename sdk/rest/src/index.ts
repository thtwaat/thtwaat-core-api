export { RestClient, REST_SDK_VERSION, default } from "./client";
export { HttpCore } from "./core/http";
export { RestError, normalizeError, isRetryableStatus } from "./core/errors";
export { withRetry, sleep } from "./core/retry";
export { normalizePage, iteratePages } from "./core/pagination";

export type {
  RestClientConfig,
  RequestOptions,
  PageParams,
  PageResult,
  HttpMethod,
  AuthMode,
} from "./core/types";

/** OpenAPI-generated types — do not edit `generated/schema.ts` by hand */
export type { paths, components, operations } from "./generated/schema";
