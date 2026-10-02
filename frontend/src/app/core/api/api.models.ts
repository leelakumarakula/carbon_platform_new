/** Shapes shared by every API call (backend: app/schemas/common.py, app/core/errors.py). */

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PageQuery {
  page?: number;
  page_size?: number;
  sort?: string | null;
}

export interface ApiErrorBody {
  success: false;
  error_code: string;
  message: string;
  details: Record<string, unknown>;
  request_id: string | null;
}

export interface FieldError {
  field: string;
  message: string;
  type?: string;
}

/** Normalised error thrown by every API call (see errorInterceptor). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }

  get fieldErrors(): FieldError[] {
    const errors = this.details['errors'];
    return Array.isArray(errors) ? (errors as FieldError[]) : [];
  }

  static from(err: unknown): ApiError {
    if (err instanceof ApiError) return err;
    return new ApiError(0, 'UNKNOWN_ERROR', err instanceof Error ? err.message : 'Something went wrong.');
  }
}

export interface MessageResponse {
  success: boolean;
  message: string;
}
