// Generated from FastAPI OpenAPI. Do not edit.
export interface paths {
    "/api/documents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Owner-scoped document list
         * @description List the verified principal's documents, newest first, owner-scoped.
         */
        get: operations["listDocuments"];
        put?: never;
        /**
         * Create an owned document with its first revision
         * @description Create an owned document whose first revision is the empty document.
         */
        post: operations["createDocument"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Fetch an owned document with content
         * @description Return the owned document with its current canonical content and ETag.
         */
        get: operations["getDocument"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Save a new immutable revision (compare-and-set via If-Match)
         * @description Append one immutable revision; CAS against If-Match, zero rows on failure.
         */
        post: operations["saveDocumentVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/home": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Owner-scoped workspace home aggregation
         * @description Return the verified principal's recent documents and scoped totals.
         *
         *     The pending sections (recent_charts, recent_insights, indicators) are
         *     honest empty arrays until NI-035 / NI-046-047 / NI-031-032 implement
         *     their data pipelines; see schemas/home.py.
         */
        get: operations["getWorkspaceHome"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** The verified principal's own profile */
        get: operations["getMe"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update the verified principal's own display name/timezone
         * @description Update the verified subject's own profile row via the near_app role.
         *
         *     The profile_self UPDATE policy only ever matches the transaction-local
         *     subject, so a foreign or disabled profile is unreachable; an empty update
         *     result is a fail-closed bootstrap error, never a cross-owner write.
         */
        patch: operations["updateMe"];
        trace?: never;
    };
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
        /**
         * DocumentCreateRequest
         * @description POST /documents body. `template_id` is P1: providing it is a typed 422.
         */
        DocumentCreateRequest: {
            /** Template Id */
            template_id?: "investment-v1" | null;
            /** Title */
            title: string;
        };
        /**
         * DocumentListResponse
         * @description GET /documents response: bounded page with an opaque next cursor.
         */
        DocumentListResponse: {
            /** Items */
            items: components["schemas"]["DocumentSummary"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * DocumentProgress
         * @description Per-document work-completion counters (`{headings,charts,insights}`).
         *
         *     Block projection regeneration is owned by the document revision service
         *     (NI-036) and the chart/insight block taxonomy by NI-041/NI-046/NI-047.
         *     Until that canonical taxonomy and projection exist, these counters are
         *     the documented zero; they are never guessed from a non-canonical block
         *     type naming. The counter semantics measure work completion only.
         */
        DocumentProgress: {
            /** Charts */
            charts: number;
            /** Headings */
            headings: number;
            /** Insights */
            insights: number;
        };
        /**
         * DocumentResponse
         * @description `Document` = DocumentSummary plus current canonical content.
         */
        DocumentResponse: {
            /** Content */
            content: {
                [key: string]: unknown;
            };
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Current Version Id */
            current_version_id: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            progress: components["schemas"]["DocumentProgress"];
            /** Resolved Contexts */
            resolved_contexts: {
                [key: string]: unknown;
            };
            /** Revision */
            revision: number;
            /** Schema Version */
            schema_version: number;
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * DocumentSaveRequest
         * @description POST /documents/{id}/versions body (If-Match header carries the CAS).
         */
        DocumentSaveRequest: {
            /** Content */
            content: {
                [key: string]: unknown;
            };
            /**
             * Observed Contexts
             * @default []
             */
            observed_contexts: {
                [key: string]: unknown;
            }[];
            /** Schema Version */
            schema_version: number;
        };
        /**
         * DocumentSaveResponse
         * @description 201 body of the save route: the new revision plus the moved summary.
         */
        DocumentSaveResponse: {
            document: components["schemas"]["DocumentSummary"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /**
         * DocumentSummary
         * @description Current-revision summary of an owned document.
         *
         *     `revision`/`current_version_id` come from the live app.documents row, so
         *     a summary always reflects the document's current revision. A document
         *     that has no saved revision yet carries `current_version_id: null`.
         */
        DocumentSummary: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Current Version Id */
            current_version_id: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            progress: components["schemas"]["DocumentProgress"];
            /** Revision */
            revision: number;
            /** Schema Version */
            schema_version: number;
            /** Title */
            title: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
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
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
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
        /**
         * HomeCounts
         * @description Owner-scoped workflow totals the workspace shell renders.
         *
         *     Only the documents total exists today (it is the scoped count of the same
         *     statement that pages recent_documents). Sections that arrive with
         *     NI-035/NI-046/NI-047 extend this object instead of reshaping the response.
         */
        HomeCounts: {
            /** Documents */
            documents: number;
        };
        /**
         * HomeResponse
         * @description `GET /api/home` payload for the verified principal.
         *
         *     Operator-directed addition to the specification row: `counts` exposes the
         *     owner-scoped totals (NI-022 "include workflow counts"). Every list is
         *     capped at RECENT_LIST_CAP by the query, not by slicing.
         */
        HomeResponse: {
            counts: components["schemas"]["HomeCounts"];
            /** Indicators */
            indicators: components["schemas"]["PendingHomeSection"][];
            /** Recent Charts */
            recent_charts: components["schemas"]["PendingHomeSection"][];
            /** Recent Documents */
            recent_documents: components["schemas"]["DocumentSummary"][];
            /** Recent Insights */
            recent_insights: components["schemas"]["PendingHomeSection"][];
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
        /**
         * PendingHomeSection
         * @description Typed marker element for a home section whose data model arrives later.
         *
         *     recent_charts arrives with NI-035 (persisted saved charts), recent_insights
         *     with NI-046/NI-047 (insight contracts and persistence) and indicators with
         *     NI-031/NI-032 (versioned chart/metric registries and public series APIs).
         *     The owning tasks replace this element type with SavedChart / Insight /
         *     Series per API_SPECIFICATION.md. The response schema forbids items
         *     (`maxItems: 0`) until then: an empty array is the honest answer and
         *     fabricated placeholder data can never validate.
         */
        PendingHomeSection: {
            /**
             * Status
             * @default pending
             * @constant
             */
            status: "pending";
        };
        /** ProfileResponse */
        ProfileResponse: {
            /** Display Name */
            display_name: string;
            /** Display Timezone */
            display_timezone: string;
            /** Subject */
            subject: string;
        };
        /** ProfileUpdateRequest */
        ProfileUpdateRequest: {
            /** Display Name */
            display_name: string;
            /** Display Timezone */
            display_timezone: string;
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
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** VersionDetailResponse */
        VersionDetailResponse: {
            /** Content */
            content: {
                [key: string]: unknown;
            };
            /** Content Sha256 */
            content_sha256: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Resolved Contexts */
            resolved_contexts: {
                [key: string]: unknown;
            };
            /** Revision */
            revision: number;
            /** Schema Version */
            schema_version: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    listDocuments: {
        parameters: {
            query?: {
                q?: string | null;
                cursor?: string | null;
                limit?: number | null;
            };
            header?: {
                authorization?: string | null;
            };
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
                    "application/json": components["schemas"]["DocumentListResponse"];
                };
            };
            /** @description Missing or invalid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Verified account is disabled */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Referenced target does not exist for this owner */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Revision conflict: the document moved since the request was built */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Document exceeds a hard size limit */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description If-Match precondition is required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createDocument: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DocumentCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentResponse"];
                };
            };
            /** @description Missing or invalid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Verified account is disabled */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Referenced target does not exist for this owner */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Revision conflict: the document moved since the request was built */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Document exceeds a hard size limit */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description If-Match precondition is required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getDocument: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
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
                    "application/json": components["schemas"]["DocumentResponse"];
                };
            };
            /** @description Missing or invalid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Verified account is disabled */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Referenced target does not exist for this owner */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Revision conflict: the document moved since the request was built */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Document exceeds a hard size limit */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description If-Match precondition is required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    saveDocumentVersion: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DocumentSaveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentSaveResponse"];
                };
            };
            /** @description Missing or invalid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Verified account is disabled */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Referenced target does not exist for this owner */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Revision conflict: the document moved since the request was built */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Document exceeds a hard size limit */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description If-Match precondition is required */
            428: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    getWorkspaceHome: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
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
                    "application/json": components["schemas"]["HomeResponse"];
                };
            };
            /** @description Missing or invalid session */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Verified account is disabled */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Referenced target does not exist for this owner */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    getMe: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
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
                    "application/json": components["schemas"]["ProfileResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    updateMe: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProfileUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProfileResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
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
