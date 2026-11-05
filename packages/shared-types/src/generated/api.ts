// Generated from FastAPI OpenAPI. Do not edit.
export interface paths {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health
         * @description Process liveness mirroring the web service /health JSON shape.
         */
        get: operations["getHealth"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ApiError */
        ApiError: {
            /** Code */
            code: string;
            /** Details */
            details?: components["schemas"]["ErrorDetail"][] | null;
            /** Message */
            message: string;
            /**
             * Request Id
             * Format: uuid
             */
            request_id: string;
            /** Retryable */
            retryable: boolean;
        };
        /** Coverage */
        Coverage: {
            /** Expected */
            expected: number;
            /** Observed */
            observed: number;
        };
        /** DataQuality */
        DataQuality: {
            /** Bound Kind */
            bound_kind: ("exact" | "estimate" | "lower" | "upper") | null;
            coverage: components["schemas"]["Coverage"];
            /** Freshness Target Seconds */
            freshness_target_seconds: number | null;
            /** Reasons */
            reasons: components["schemas"]["Reason"][];
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "partial" | "missing" | "stale" | "unavailable" | "revised";
        };
        DecimalString: string;
        /** ErrorDetail */
        ErrorDetail: {
            /** Path */
            path: string;
            reason: components["schemas"]["Reason"];
        };
        /** ErrorResponse */
        ErrorResponse: {
            error: components["schemas"]["ApiError"];
        };
        /** HealthResponse */
        HealthResponse: {
            /**
             * Appenv
             * @enum {string}
             */
            appEnv: "development" | "test" | "production";
            /**
             * Checkedat
             * Format: date-time
             */
            checkedAt: string;
            /**
             * Service
             * @constant
             */
            service: "api";
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /** Observation */
        Observation: {
            /**
             * End
             * Format: date-time
             */
            end: string;
            quality: components["schemas"]["DataQuality"];
            /**
             * Start
             * Format: date-time
             */
            start: string;
            value: components["schemas"]["DecimalString"] | null;
        };
        Reason: string;
        /** Selection */
        Selection: {
            /**
             * End
             * Format: date
             */
            end: string;
            filters: components["schemas"]["SelectionFilters"];
            /**
             * Frequency
             * @constant
             */
            frequency: "day";
            /**
             * Start
             * Format: date
             */
            start: string;
        };
        /**
         * SelectionFilters
         * @description No filter is approved at bootstrap; NI-031 adds versioned filter rules.
         */
        SelectionFilters: Record<string, never>;
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    getHealth: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Invalid server configuration */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
}
