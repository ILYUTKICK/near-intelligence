// Generated from FastAPI OpenAPI. Do not edit.
export interface paths {
    "/api/charts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Public chart definition catalog
         * @description List the latest registered version of every chart definition.
         */
        get: operations["listCharts"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/charts/{chart_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One chart definition version
         * @description Return one registered chart definition (latest version by default).
         */
        get: operations["getChart"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/charts/{chart_id}/view": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Resolved chart view pinned to one approved dataset version
         * @description Resolve the chart view: definition, series, quality and context hash.
         */
        get: operations["getChartView"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data-sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Sanitized public source catalog
         * @description List the sanitized source projections (never provider endpoints).
         */
        get: operations["listDataSources"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/data-sources/{source_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One sanitized source projection
         * @description Return one source's sanitized projection (missing sources are 404).
         */
        get: operations["getDataSource"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/datasets/{version_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One approved immutable dataset version
         * @description Return one approved dataset version; non-approved versions are 404.
         */
        get: operations["getDataset"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/datasets/{version_id}/manifest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Sanitized prepared manifest of one approved dataset version
         * @description Serve the sanitized manifest: storage digests, never operator paths.
         */
        get: operations["getDatasetManifest"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
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
         *
         *     With an ``Idempotency-Key`` header the created result is stored in the
         *     write transaction and a repeated identical owner/route/body request
         *     replays the original 201 response (24h) instead of creating a second
         *     document; the same key with a different body is a 409 idempotency
         *     collision.
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
        /**
         * Delete an owned document with its private revisions and projections
         * @description Delete the owned document; private children cascade, scientific data stays.
         */
        delete: operations["deleteDocument"];
        options?: never;
        head?: never;
        /**
         * Rename an owned document (a title change creates a new revision)
         * @description Rename the owned document; the title change is a full new revision.
         */
        patch: operations["renameDocument"];
        trace?: never;
    };
    "/api/documents/{document_id}/chart-blocks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Append one inspected chart block to an owned document (compare-and-set via If-Match)
         * @description Append one valid liveChart block with its frozen inspection context.
         *
         *     With an ``Idempotency-Key`` the response snapshot is stored in the write
         *     transaction (NI-037 store), so a repeated identical owner/route/body
         *     request replays the original 201 (same revision, no second block)
         *     instead of a spurious 409 against the advanced document.
         */
        post: operations["addChartBlock"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/chart-view": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Inspect one canonical chart context for an owned working document
         * @description Resolve an editor inspection through the canonical public chart adapter.
         *
         *     The dataset choice is REQUIRED: normal reopen/range/filter requests send
         *     the observed immutable UUID; only an explicit Refresh sends ``latest``.
         *     Resolution does not mutate the document. A successful explicit editor
         *     action adopts the returned selection + dataset UUID in one undoable edit,
         *     and the ordinary CAS revision save validates and freezes those attrs.
         *     New/duplicated unsaved blocks can be inspected too, without requiring a
         *     persisted block id. The latest approved UUID is separate metadata so a
         *     publication can be signaled while the inspected data stays pinned.
         */
        get: operations["getDocumentChartView"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/evidence": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List evidence in a current or historical owned document revision */
        get: operations["listDocumentEvidence"];
        put?: never;
        /** Add evidence to an owned document */
        post: operations["createDocumentEvidence"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/evidence-targets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List selectable public evidence targets for an owned document */
        get: operations["listDocumentEvidenceTargets"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/evidence/{evidence_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove evidence from the current owned document revision */
        delete: operations["deleteDocumentEvidence"];
        options?: never;
        head?: never;
        /** Edit evidence in the current owned document revision */
        patch: operations["updateDocumentEvidence"];
        trace?: never;
    };
    "/api/documents/{document_id}/exports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create (idempotently) the Markdown ZIP export job of the acknowledged revision
         * @description Queue one Markdown ZIP export of the owned document's current revision.
         *
         *     The frozen export plan is built in the same transaction that inserts the
         *     job (NI-056): the requested revision must be the document's acknowledged
         *     current version — a valid but superseded revision is the typed 409
         *     ``REVISION_NOT_ACKNOWLEDGED`` (save/rename again and export the new
         *     current revision), and an unresolvable pin or reference is the typed 422.
         *     With an ``Idempotency-Key: UUID`` a repeated identical owner/route/body
         *     request replays the ORIGINAL job instead of creating a second one; the
         *     same key with a different body is a 409 idempotency collision.
         */
        post: operations["createDocumentExport"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/exports/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Poll one owned export job (typed lifecycle states)
         * @description Return the export job's typed state, computed at read time.
         *
         *     ``expired`` is reported the moment the artifact TTL passes — before and
         *     independently of the worker's documented sweep — so the state is always
         *     honest.
         */
        get: operations["getDocumentExport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/exports/{job_id}/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download the finished export ZIP (owner-only, unexpired)
         * @description Stream the stored ZIP of one succeeded, unexpired export job.
         *
         *     The bytes are re-verified against the job's recorded SHA-256 before they
         *     are returned; anything else (queued/running, failed, expired, corrupt)
         *     is a typed refusal — never a stale or altered file.
         */
        get: operations["downloadDocumentExport"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/hypotheses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List hypotheses in a current or historical owned document revision */
        get: operations["listDocumentHypotheses"];
        put?: never;
        /** Add a hypothesis to an owned document */
        post: operations["createDocumentHypothesis"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/hypotheses/{hypothesis_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove a hypothesis with explicitly confirmed reference cleanup */
        delete: operations["deleteDocumentHypothesis"];
        options?: never;
        head?: never;
        /** Edit a hypothesis in the current owned document revision */
        patch: operations["updateDocumentHypothesis"];
        trace?: never;
    };
    "/api/documents/{document_id}/insights": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List insights in a current or historical owned document revision */
        get: operations["listDocumentInsights"];
        put?: never;
        /** Add an inspected chart insight to an owned document */
        post: operations["createDocumentInsight"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/insights/{insight_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /** Remove an insight with explicitly confirmed evidence cleanup */
        delete: operations["deleteDocumentInsight"];
        options?: never;
        head?: never;
        /** Edit an insight in the current owned document revision */
        patch: operations["updateDocumentInsight"];
        trace?: never;
    };
    "/api/documents/{document_id}/versions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List an owned document's immutable revisions (newest first)
         * @description Page the owned document's revisions over the stable revision DESC order.
         */
        get: operations["listDocumentVersions"];
        put?: never;
        /**
         * Save a new immutable revision (compare-and-set via If-Match)
         * @description Append one immutable revision; CAS against If-Match, zero rows on failure.
         *
         *     With an ``Idempotency-Key`` the new revision's response snapshot is stored
         *     in the save transaction, so a retry of the identical owner/route/body
         *     request after a lost response replays the original 201 (same version, no
         *     second revision) instead of a spurious 409 against the advanced document.
         */
        post: operations["saveDocumentVersion"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/versions/{version_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Fetch one immutable revision of an owned document
         * @description Return the revision only through its owned parent document.
         */
        get: operations["getDocumentVersion"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/csv": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Download exact chart data from an owned immutable revision */
        get: operations["getDocumentVersionChartCsv"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/documents/{document_id}/versions/{version_id}/chart-blocks/{block_id}/view": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Reconstruct one chart from an owned immutable revision */
        get: operations["getDocumentVersionChartView"];
        put?: never;
        post?: never;
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
         *     Private lists use current owner-scoped projections. Each approved public
         *     indicator resolves independently; source failures do not hide research.
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
    "/api/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Public metric definition catalog
         * @description List the latest registered version of every metric definition.
         */
        get: operations["listMetrics"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics/{metric_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One metric definition version
         * @description Return one registered metric definition (latest version by default).
         */
        get: operations["getMetric"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/metrics/{metric_id}/series": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Resolved metric series from one approved dataset version
         * @description Resolve the metric's series over the selection from one approved dataset.
         */
        get: operations["getMetricSeries"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/model-definitions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Public model definitions (published specifications only)
         * @description List definitions derived from published runs (never from local reports).
         */
        get: operations["listModelDefinitions"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/model-definitions/{model_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One public model definition
         * @description One specification's definition from its latest published run.
         */
        get: operations["getModelDefinition"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/model-definitions/{model_id}/readiness": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * NI-051 gate verdict for one specification (public)
         * @description The recorded gate verdict; a never-published verdict is the same 404.
         */
        get: operations["getModelReadiness"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/model-runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Catalog of published model runs
         * @description List published runs newest-first (unpublished runs are never listed).
         */
        get: operations["listModelRuns"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/model-runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * One published run with its results
         * @description Return one published run; non-published identities are the same 404.
         */
        get: operations["getModelRun"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/model-runs/{run_id}/manifest": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Downloadable manifest bundle of one published run
         * @description Serve the verified bundle verbatim; ``research verify --bundle`` accepts it.
         */
        get: operations["getModelRunManifest"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/saved-charts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Saved */
        get: operations["listSavedCharts"];
        put?: never;
        /** Create Saved */
        post: operations["createSavedChart"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/saved-charts/{instance_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Saved */
        get: operations["getSavedChart"];
        put?: never;
        post?: never;
        /** Delete Saved */
        delete: operations["deleteSavedChart"];
        options?: never;
        head?: never;
        /** Update Saved */
        patch: operations["updateSavedChart"];
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
        /**
         * ApprovalResponse
         * @description The recorded operator review provenance of a published run.
         */
        ApprovalResponse: {
            /**
             * Decision
             * @constant
             */
            decision: "approve";
            /** Notes */
            notes?: string | null;
            /** Review Reference */
            review_reference: string;
            /** Reviewed At */
            reviewed_at?: string | null;
            /** Reviewer */
            reviewer: string;
        };
        /**
         * AvailableRanges
         * @description Bounded query ranges of a chart definition (registry ``allowed_ranges``).
         */
        AvailableRanges: {
            /** Max Days */
            max_days: number;
            /** Presets Days */
            presets_days: number[];
        };
        /**
         * ChartBlockInsertRequest
         * @description POST /documents/{id}/chart-blocks body (If-Match carries the CAS).
         *
         *     ``dataset_version_id`` is the INSPECTED dataset version from the
         *     explorer/library/detail view: the server pins exactly that version and
         *     rejects the request when it is not an approved public dataset — it never
         *     substitutes latest (API_SPECIFICATION: "Server accepts the inspected
         *     dataset version to prevent data changing between preview and insertion").
         *     ``after_block_id`` positions the new block after an existing top-level
         *     block of the document; without it the block is appended last.
         */
        ChartBlockInsertRequest: {
            /** After Block Id */
            after_block_id?: string | null;
            /**
             * Chart Definition Version Id
             * Format: uuid
             */
            chart_definition_version_id: string;
            /**
             * Dataset Version Id
             * Format: uuid
             */
            dataset_version_id: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "live" | "snapshot";
            selection: components["schemas"]["ChartSelection"];
            /** Snapshot Id */
            snapshot_id?: string | null;
        };
        /**
         * ChartBlockMutationResponse
         * @description ``MutationResult<{block_id}>``: the new revision summary plus the block.
         *
         *     The new revision's content and resolved contexts (including the frozen
         *     context of the inserted block, keyed by ``block_id``) are fetchable
         *     through ``GET /documents/{id}`` — the response never makes the client
         *     guess the new revision (the ETag carries it).
         */
        ChartBlockMutationResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["ChartBlockValue"];
        };
        /**
         * ChartBlockValue
         * @description The inserted block identity (API_SPECIFICATION ``MutationResult`` value).
         */
        ChartBlockValue: {
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
        };
        /**
         * ChartDefinitionResponse
         * @description One immutable chart definition version (API_SPECIFICATION ``ChartDefinition``).
         *
         *     ``data_status`` is the honest advertisement: only ``available`` charts may
         *     be rendered as live; ``unavailable`` charts always carry their recorded
         *     reason and are never advertised as live.
         */
        ChartDefinitionResponse: {
            available_ranges: components["schemas"]["AvailableRanges"];
            /**
             * Category
             * @enum {string}
             */
            category: "activity" | "fees" | "treasury" | "supply" | "model";
            /** Chart Id */
            chart_id: string;
            /**
             * Data Status
             * @enum {string}
             */
            data_status: "available" | "unavailable";
            /** Description */
            description: string;
            /** Filter Schema */
            filter_schema: {
                [key: string]: unknown;
            };
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Metric Definition Ids */
            metric_definition_ids: string[];
            /** Renderer Version */
            renderer_version: string;
            /** Source Lineage */
            source_lineage: {
                [key: string]: unknown;
            };
            /** Title */
            title: string;
            /** Unavailable Reason */
            unavailable_reason?: string | null;
            /** Units */
            units: {
                [key: string]: string;
            };
            /**
             * Update Frequency
             * @enum {string}
             */
            update_frequency: "daily" | "weekly" | "monthly" | "snapshot";
            /** Version */
            version: number;
            /**
             * Visualization Type
             * @enum {string}
             */
            visualization_type: "line" | "area" | "bar" | "scatter" | "panels";
        };
        /** ChartListResponse */
        ChartListResponse: {
            /** Items */
            items: components["schemas"]["ChartDefinitionResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** ChartSelection */
        ChartSelection: {
            /**
             * End
             * Format: date
             */
            end: string;
            /** Filters */
            filters: {
                [key: string]: string[];
            };
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
         * ChartViewResponse
         * @description Resolved renderer-agnostic chart view (API_SPECIFICATION ``ChartView``).
         *
         *     ``context_hash`` covers the chart definition version, the pinned dataset
         *     version, the canonical selection (including validated filters) and the
         *     bound metric definition versions, so identical selections hash identically
         *     and any changed input changes the hash.
         */
        ChartViewResponse: {
            /** Context Hash */
            context_hash: string;
            dataset: components["schemas"]["DatasetResponse"];
            definition: components["schemas"]["ChartDefinitionResponse"];
            quality: components["schemas"]["DataQuality"];
            /**
             * Resolved At
             * Format: date-time
             */
            resolved_at: string;
            selection: components["schemas"]["ResolvedSelection"];
            /** Series */
            series: components["schemas"]["SeriesResponse"][];
        };
        /**
         * CoefficientResponse
         * @description One recorded coefficient of a published fit (API_SPECIFICATION ``ModelRun``
         *     ``coefficients`` row: term/estimate/standard_error/ci bounds/p_value).
         *
         *     Values are the fit manifest's finite float64 records verbatim; the
         *     publication gate refuses NaN/Infinity, so a published coefficient is
         *     always finite. ``p_value`` is recorded evidence, never a selection input.
         */
        CoefficientResponse: {
            /** Ci95 High */
            ci95_high?: number;
            /** Ci95 Low */
            ci95_low?: number;
            /** Estimate */
            estimate?: number;
            /** Name */
            name: string;
            /** P Value */
            p_value?: number;
            /** Std Error */
            std_error?: number;
            /** T Stat */
            t_stat?: number;
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
        /** DataSourceListResponse */
        DataSourceListResponse: {
            /** Items */
            items: components["schemas"]["DataSourceResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * DataSourceResponse
         * @description Sanitized source projection (API_SPECIFICATION ``DataSource``).
         *
         *     The provider endpoint (``base_url``) and every credential-bearing value
         *     are never serialized: ``docs_url`` is nulled unless it is a credential-free
         *     http(s) URL. ``expected_update_frequency`` stays null until the operator
         *     catalog records it (missing is not fabricated); ``last_success_at`` comes
         *     from the ingestion checkpoint zone when the source has been refreshed.
         */
        DataSourceResponse: {
            /**
             * Access Status
             * @enum {string}
             */
            access_status: "disabled" | "documented" | "approved";
            /** Docs Url */
            docs_url: string | null;
            /** Expected Update Frequency */
            expected_update_frequency: string | null;
            /** Id */
            id: string;
            /** Last Success At */
            last_success_at: string | null;
            /**
             * License Status
             * @enum {string}
             */
            license_status: "unknown" | "unverified" | "verified" | "prohibited";
            /** Lineage */
            lineage: string[];
            /** Name */
            name: string;
            /** Verified At */
            verified_at: string | null;
        };
        /**
         * DatasetResponse
         * @description One approved immutable dataset version (API_SPECIFICATION ``Dataset``).
         *
         *     Public delivery serves ``approved`` versions only: staged, validated and
         *     rejected versions are indistinguishable from absent ones (404) and can
         *     never appear under ``latest``.
         */
        DatasetResponse: {
            /** Content Sha256 */
            content_sha256: string;
            /** Dataset Key */
            dataset_key: string;
            /**
             * End
             * Format: date
             */
            end: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Manifest Url */
            manifest_url: string | null;
            /** Pipeline Version */
            pipeline_version: string;
            quality: components["schemas"]["DataQuality"];
            /** Retrieved At */
            retrieved_at: string | null;
            /** Source As Of */
            source_as_of: string | null;
            /**
             * Start
             * Format: date
             */
            start: string;
            /**
             * Status
             * @constant
             */
            status: "approved";
            /** Supersedes Id */
            supersedes_id: string | null;
            /** Version */
            version: number;
        };
        DecimalString: string;
        /**
         * DocumentChartViewResponse
         * @description Working-view data plus the current compatible approved dataset pointer.
         */
        DocumentChartViewResponse: {
            /** Context Hash */
            context_hash: string;
            dataset: components["schemas"]["DatasetResponse"];
            definition: components["schemas"]["ChartDefinitionResponse"];
            /** Latest Approved Dataset Version Id */
            latest_approved_dataset_version_id: string | null;
            quality: components["schemas"]["DataQuality"];
            /**
             * Resolved At
             * Format: date-time
             */
            resolved_at: string;
            selection: components["schemas"]["ResolvedSelection"];
            /** Series */
            series: components["schemas"]["SeriesResponse"][];
        };
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
         * DocumentExportRequest
         * @description POST /documents/{id}/exports body.
         *
         *     ``document_version_id`` must be the document's acknowledged current
         *     revision at request time (API_SPECIFICATION: "Client first saves then
         *     uses acknowledged version ID") — the frozen plan is built only while the
         *     requested revision is current, so title and content always describe the
         *     same revision. A valid but superseded revision is a typed 409.
         */
        DocumentExportRequest: {
            /**
             * Document Version Id
             * Format: uuid
             */
            document_version_id: string;
            /**
             * Format
             * @enum {string}
             */
            format: "markdown_zip" | "pdf";
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
         *     Home counts the canonical current-version heading/liveChart/insight
         *     projection types. The counter semantics measure work completion only.
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
         * DocumentRenameRequest
         * @description PATCH /documents/{id} body: the new title (a title change creates a
         *     full new revision — EDITOR_SPECIFICATION; an unchanged title is a no-op).
         */
        DocumentRenameRequest: {
            /** Title */
            title: string;
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
            observed_contexts: components["schemas"]["ResolvedContext"][];
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
        /**
         * Evidence
         * @description API_SPECIFICATION ``Evidence``: EvidenceInput plus server fields.
         *
         *     ``authored_at``/``modified_at`` are response metadata authored by the
         *     server; the canonical evidence node itself stays timestamp-free per
         *     EDITOR_SPECIFICATION (timestamps live on the revision that carries it).
         */
        Evidence: {
            /**
             * Authored At
             * Format: date-time
             */
            authored_at: string;
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Explanation */
            explanation: string;
            /**
             * Hypothesis Id
             * Format: uuid
             */
            hypothesis_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Modified At
             * Format: date-time
             */
            modified_at: string;
            /**
             * Target Id
             * Format: uuid
             */
            target_id: string;
            /**
             * Target Kind
             * @enum {string}
             */
            target_kind: "insight" | "chart_block" | "model_run" | "citation";
        };
        /**
         * EvidenceCreateRequest
         * @description Append, insert after a current block, or convert a current paragraph.
         */
        EvidenceCreateRequest: {
            /** After Block Id */
            after_block_id?: string | null;
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            /** Explanation */
            explanation: string;
            /**
             * Hypothesis Id
             * Format: uuid
             */
            hypothesis_id: string;
            /**
             * Target Id
             * Format: uuid
             */
            target_id: string;
            /**
             * Target Kind
             * @enum {string}
             */
            target_kind: "insight" | "chart_block" | "model_run" | "citation";
        };
        /** EvidenceDeleteResponse */
        EvidenceDeleteResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["EvidenceDeleteValue"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /** EvidenceDeleteValue */
        EvidenceDeleteValue: {
            /**
             * Deleted Id
             * Format: uuid
             */
            deleted_id: string;
        };
        /**
         * EvidenceInput
         * @description POST /documents/{id}/evidence body (API_SPECIFICATION ``EvidenceInput``).
         *
         *     ``target_kind``/``target_id`` must resolve to an allowed typed target in
         *     the same revision or to a public immutable artifact; that visibility/
         *     reference validation is service scope (NI-049) — this contract rejects the
         *     shapes it can reject (unknown kinds, non-UUID ids, unbounded explanation).
         */
        EvidenceInput: {
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            /** Explanation */
            explanation: string;
            /**
             * Hypothesis Id
             * Format: uuid
             */
            hypothesis_id: string;
            /**
             * Target Id
             * Format: uuid
             */
            target_id: string;
            /**
             * Target Kind
             * @enum {string}
             */
            target_kind: "insight" | "chart_block" | "model_run" | "citation";
        };
        /** EvidenceMutationResponse */
        EvidenceMutationResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["Evidence"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /**
         * EvidencePatchRequest
         * @description Edit the relationship and explanation while retaining its identity.
         */
        EvidencePatchRequest: {
            /**
             * Classification
             * @enum {string}
             */
            classification?: "supporting" | "contradicting" | "uncertain";
            /** Explanation */
            explanation?: string;
            /**
             * Hypothesis Id
             * Format: uuid
             */
            hypothesis_id?: string;
            /**
             * Target Id
             * Format: uuid
             */
            target_id?: string;
            /**
             * Target Kind
             * @enum {string}
             */
            target_kind?: "insight" | "chart_block" | "model_run" | "citation";
        };
        /** EvidenceTarget */
        EvidenceTarget: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Label */
            label: string;
        };
        /** EvidenceTargetListResponse */
        EvidenceTargetListResponse: {
            /** Items */
            items: components["schemas"]["EvidenceTarget"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * ExportJobResponse
         * @description The typed lifecycle state of one owned export job.
         *
         *     ``download_path`` is the same-origin owner-checked download route and is
         *     set only while the bundle is downloadable (``succeeded`` and unexpired);
         *     ``error_code`` is set exactly when ``status`` is ``failed``. No field of
         *     this response carries a server filesystem path or a credential.
         */
        ExportJobResponse: {
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /**
             * Document Version Id
             * Format: uuid
             */
            document_version_id: string;
            /** Download Path */
            download_path?: string | null;
            /** Error Code */
            error_code?: string | null;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Format
             * @constant
             */
            format: "markdown_zip";
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Status
             * @enum {string}
             */
            status: "queued" | "running" | "succeeded" | "failed" | "expired";
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
         * @description Owner-scoped document total; no financial or confidence meaning.
         */
        HomeCounts: {
            /** Documents */
            documents: number;
        };
        /**
         * HomeIndicator
         * @description One canonical single-day series or an independently unavailable context.
         *
         *     The series preserves metric/dataset versions, decimal strings, quality,
         *     source provenance and the exact UTC selection. No home-specific arithmetic.
         */
        HomeIndicator: {
            /** Chart Id */
            chart_id: string;
            /** Chart Version */
            chart_version: number | null;
            /** Reason */
            reason: string | null;
            series: components["schemas"]["SeriesResponse"] | null;
            /**
             * Status
             * @enum {string}
             */
            status: "available" | "unavailable";
            /** Title */
            title: string;
        };
        /**
         * HomeInsightSummary
         * @description An existing canonical insight in an owned document's current revision.
         *
         *     This read projection provides navigation only; NI-047 owns insight authoring.
         */
        HomeInsightSummary: {
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Document Title */
            document_title: string;
            /** Excerpt */
            excerpt: string;
            /**
             * Insight Id
             * Format: uuid
             */
            insight_id: string;
            /**
             * Modified At
             * Format: date-time
             */
            modified_at: string;
            /**
             * Type
             * @enum {string}
             */
            type: "observation" | "hypothesis" | "risk" | "conclusion";
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
            indicators: components["schemas"]["HomeIndicator"][];
            /** Recent Charts */
            recent_charts: components["schemas"]["SavedChartResponse"][];
            /** Recent Documents */
            recent_documents: components["schemas"]["DocumentSummary"][];
            /** Recent Insights */
            recent_insights: components["schemas"]["HomeInsightSummary"][];
        };
        /**
         * Hypothesis
         * @description API_SPECIFICATION ``Hypothesis``: HypothesisInput plus server fields.
         */
        Hypothesis: {
            /**
             * Assessment
             * @enum {string}
             */
            assessment: "untested" | "supported" | "mixed" | "weakened" | "insufficient_data";
            /**
             * Authored At
             * Format: date-time
             */
            authored_at: string;
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
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
            /**
             * Modified At
             * Format: date-time
             */
            modified_at: string;
            /** Statement */
            statement: string;
        };
        /**
         * HypothesisCreateRequest
         * @description Append, insert after a current block, or convert a current paragraph.
         */
        HypothesisCreateRequest: {
            /** After Block Id */
            after_block_id?: string | null;
            /**
             * Assessment
             * @enum {string}
             */
            assessment: "untested" | "supported" | "mixed" | "weakened" | "insufficient_data";
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /** Statement */
            statement: string;
        };
        /** HypothesisDeleteRequest */
        HypothesisDeleteRequest: {
            /** Remove Evidence Links */
            remove_evidence_links: boolean;
        };
        /** HypothesisDeleteResponse */
        HypothesisDeleteResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["HypothesisDeleteValue"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /** HypothesisDeleteValue */
        HypothesisDeleteValue: {
            /**
             * Deleted Id
             * Format: uuid
             */
            deleted_id: string;
        };
        /**
         * HypothesisInput
         * @description POST /documents/{id}/hypotheses body (API_SPECIFICATION ``HypothesisInput``).
         *
         *     ``assessment`` is an authored state with rationale in the document, never
         *     an automatic truth badge; unsupported values are rejected.
         */
        HypothesisInput: {
            /**
             * Assessment
             * @enum {string}
             */
            assessment: "untested" | "supported" | "mixed" | "weakened" | "insufficient_data";
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /** Statement */
            statement: string;
        };
        /** HypothesisMutationResponse */
        HypothesisMutationResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["Hypothesis"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /**
         * HypothesisPatchRequest
         * @description Edit the statement or the manually authored assessment.
         */
        HypothesisPatchRequest: {
            /**
             * Assessment
             * @enum {string}
             */
            assessment?: "untested" | "supported" | "mixed" | "weakened" | "insufficient_data";
            /** Statement */
            statement?: string;
        };
        /**
         * Insight
         * @description API_SPECIFICATION ``Insight``: InsightInput plus server-authored fields.
         *
         *     ``id`` is the stable entity id allocated once at creation (uuid4) and kept
         *     unchanged across revisions so outline anchors and evidence references stay
         *     valid; ``document_id`` comes from the verified parent; the timestamps are
         *     authored by the server (``PATCH`` preserves the original ``authored_at``).
         */
        Insight: {
            /**
             * Authored At
             * Format: date-time
             */
            authored_at: string;
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /** Body */
            body: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList-Output"])[];
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            /** Context */
            context: components["schemas"]["ResolvedContext"] | components["schemas"]["ModelContext"];
            /**
             * Document Id
             * Format: uuid
             */
            document_id: string;
            /** Hypothesis Id */
            hypothesis_id?: string | null;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Modified At
             * Format: date-time
             */
            modified_at: string;
            /**
             * Type
             * @enum {string}
             */
            type: "observation" | "hypothesis" | "risk" | "conclusion";
        };
        /**
         * InsightCreateRequest
         * @description Create a chart insight, optionally inserting it after a current block.
         */
        InsightCreateRequest: {
            /** After Block Id */
            after_block_id?: string | null;
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /** Body */
            body: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList-Input"])[];
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            context: components["schemas"]["ResolvedContext"];
            /** Hypothesis Id */
            hypothesis_id?: string | null;
            /**
             * Type
             * @enum {string}
             */
            type: "observation" | "hypothesis" | "risk" | "conclusion";
        };
        /** InsightDeleteRequest */
        InsightDeleteRequest: {
            /** Remove Evidence Links */
            remove_evidence_links: boolean;
        };
        /** InsightDeleteResponse */
        InsightDeleteResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["InsightDeleteValue"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /** InsightDeleteValue */
        InsightDeleteValue: {
            /**
             * Deleted Id
             * Format: uuid
             */
            deleted_id: string;
        };
        /**
         * InsightInput
         * @description POST /documents/{id}/insights body (API_SPECIFICATION ``InsightInput``).
         *
         *     The insight TYPE carries the research role (observation/hypothesis/risk/
         *     conclusion); ``classification`` records how the observation relates to the
         *     linked hypothesis (supporting/contradicting/uncertain — a classification,
         *     never an inferred causal claim). ``body`` is bounded/sanitized rich text
         *     (max 10k plain-text-equivalent characters); ``context`` is the frozen
         *     inspection record the insight must stay tied to after live refresh.
         *     ``authored_at``/``modified_at`` do not exist here by construction: the
         *     server authors them.
         */
        InsightInput: {
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /** Body */
            body: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList"])[];
            /**
             * Classification
             * @enum {string}
             */
            classification: "supporting" | "contradicting" | "uncertain";
            /** Context */
            context: components["schemas"]["ResolvedContext"] | components["schemas"]["ModelContext"];
            /** Hypothesis Id */
            hypothesis_id?: string | null;
            /**
             * Type
             * @enum {string}
             */
            type: "observation" | "hypothesis" | "risk" | "conclusion";
        };
        /** InsightMutationResponse */
        InsightMutationResponse: {
            document: components["schemas"]["DocumentSummary"];
            value: components["schemas"]["Insight"];
            version: components["schemas"]["VersionDetailResponse"];
        };
        /**
         * InsightPatchRequest
         * @description Omission keeps a field. A null hypothesis_id removes the association.
         */
        InsightPatchRequest: {
            /** Body */
            body?: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList-Input"])[];
            /**
             * Classification
             * @enum {string}
             */
            classification?: "supporting" | "contradicting" | "uncertain";
            /** Context */
            context?: components["schemas"]["ResolvedContext"];
            /** Hypothesis Id */
            hypothesis_id?: string | null;
            /**
             * Type
             * @enum {string}
             */
            type?: "observation" | "hypothesis" | "risk" | "conclusion";
        };
        /**
         * LimitationsResponse
         * @description Limitations attached verbatim to the published run.
         */
        LimitationsResponse: {
            /**
             * Gate Limit Codes
             * @default []
             */
            gate_limit_codes: string[];
            /** Prohibited Labels */
            prohibited_labels: string[];
            /** Spec Limitation Notes */
            spec_limitation_notes: string[];
        };
        /** MetricListResponse */
        MetricListResponse: {
            /** Items */
            items: components["schemas"]["MetricResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * MetricResponse
         * @description One immutable metric definition version (API_SPECIFICATION ``Metric``).
         *
         *     ``formula`` is the registered computation identifier (``formula_key``) —
         *     a stable provenance label, never executable user input.
         */
        MetricResponse: {
            /**
             * Availability
             * @enum {string}
             */
            availability: "A" | "P" | "B" | "G";
            /** Definition */
            definition: string;
            /** Economic Scope */
            economic_scope: string;
            /** Formula */
            formula: string;
            /**
             * Frequency
             * @enum {string}
             */
            frequency: "daily" | "weekly" | "monthly" | "snapshot";
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Limitations */
            limitations: string[];
            /** Metric Id */
            metric_id: string;
            /** Source Id */
            source_id?: string | null;
            /** Title */
            title: string;
            /** Unit */
            unit: string;
            /** Version */
            version: number;
        };
        /**
         * ModelContext
         * @description Frozen model-run inspection record (API_SPECIFICATION ``ModelContext``).
         */
        ModelContext: {
            /** Context Hash */
            context_hash: string;
            /**
             * Dataset Version Id
             * Format: uuid
             */
            dataset_version_id: string;
            /**
             * Model Run Id
             * Format: uuid
             */
            model_run_id: string;
            /** Specification Version */
            specification_version: string;
        };
        /** ModelDefinitionListResponse */
        ModelDefinitionListResponse: {
            /** Items */
            items: components["schemas"]["ModelDefinitionResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * ModelDefinitionResponse
         * @description One public model definition (API_SPECIFICATION ``ModelDefinition`` row).
         *
         *     Served from the latest published run of the specification: an unpublished
         *     or rejected specification has no public definition. ``question`` is
         *     mechanically composed from the specification's declared fields (see the
         *     module docstring) — never an authored claim.
         */
        ModelDefinitionResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Latest Published Run Id
             * Format: uuid
             */
            latest_published_run_id: string;
            limitations: components["schemas"]["LimitationsResponse"];
            /** Model Id */
            model_id: string;
            /** Question */
            question: string;
            /** Readiness Rules */
            readiness_rules: {
                [key: string]: unknown;
            };
            /** Required Metric Ids */
            required_metric_ids: string[];
            /** Specification */
            specification: {
                [key: string]: unknown;
            };
            /** Version */
            version: number;
        };
        /**
         * ModelReadinessResponse
         * @description The NI-051 gate verdict for one specification (public readiness record).
         *
         *     ``ready`` is true only for the admitted verdicts; every reason code the
         *     gate recorded travels verbatim, and ``recorded_in_run_id`` names the
         *     published run whose readiness report carries the verdict. A specification
         *     never evaluated by a published readiness report is 404 — an unpublished
         *     gate report never looks like a verdict.
         */
        ModelReadinessResponse: {
            /** Model Id */
            model_id: string;
            /** Overall Verdict */
            overall_verdict: string;
            /** Ready */
            ready: boolean;
            /**
             * Reasons
             * @default []
             */
            reasons: components["schemas"]["ReasonCodeResponse"][];
            /**
             * Recorded In Run Id
             * Format: uuid
             */
            recorded_in_run_id: string;
            /** Selected Specification */
            selected_specification?: string | null;
            /** Verdict */
            verdict: string;
        };
        /**
         * ModelRunDetailResponse
         * @description One published run with its recorded results.
         *
         *     Every block is a projection of the verified manifests stored on the row:
         *     the specification and design verbatim, the coefficient table, the
         *     estimation summary, the NI-053 diagnostics battery, the template-rendered
         *     interpretation, the limitations verbatim, the recorded environment and
         *     reproduction contract, and the review approval. The full manifest set is
         *     downloadable at ``manifest_url``.
         */
        ModelRunDetailResponse: {
            /**
             * Admission Reasons
             * @default []
             */
            admission_reasons: components["schemas"]["ReasonCodeResponse"][];
            approval: components["schemas"]["ApprovalResponse"];
            /** Code Commit */
            code_commit: string;
            /** Coefficients */
            coefficients: components["schemas"]["CoefficientResponse"][];
            /** Design */
            design: {
                [key: string]: unknown;
            };
            /** Diagnostics */
            diagnostics: {
                [key: string]: unknown;
            };
            /** Environment */
            environment: {
                [key: string]: unknown;
            };
            /** Estimation */
            estimation: {
                [key: string]: unknown;
            };
            /**
             * Gate Verdict
             * @enum {string}
             */
            gate_verdict: "READY" | "READY_WITH_LIMITS";
            /** Interpretation */
            interpretation: {
                [key: string]: unknown;
            };
            limitations: components["schemas"]["LimitationsResponse"];
            /** Manifest Url */
            manifest_url: string;
            /** Model Id */
            model_id: string;
            /** Model Version */
            model_version: number;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Published By */
            published_by: string;
            /** Reproduction */
            reproduction: {
                [key: string]: unknown;
            };
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            sample: components["schemas"]["RunSampleResponse"];
            /** Specification */
            specification: {
                [key: string]: unknown;
            };
            tolerances: components["schemas"]["TolerancesResponse"];
        };
        /** ModelRunListResponse */
        ModelRunListResponse: {
            /** Items */
            items: components["schemas"]["ModelRunSummaryResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * ModelRunSummaryResponse
         * @description One published run in the catalog (API_SPECIFICATION ``/model-runs`` row).
         *
         *     The catalog lists published runs only; unpublished, failed or rejected
         *     runs do not exist in the backing table and are indistinguishable from
         *     absent ones.
         */
        ModelRunSummaryResponse: {
            /** Code Commit */
            code_commit: string;
            /**
             * Gate Verdict
             * @enum {string}
             */
            gate_verdict: "READY" | "READY_WITH_LIMITS";
            /** Manifest Url */
            manifest_url: string;
            /** Model Id */
            model_id: string;
            /** Model Version */
            model_version: number;
            /**
             * Published At
             * Format: date-time
             */
            published_at: string;
            /** Published By */
            published_by: string;
            /**
             * Run Id
             * Format: uuid
             */
            run_id: string;
            sample: components["schemas"]["RunSampleResponse"];
            tolerances: components["schemas"]["TolerancesResponse"];
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
        /**
         * ReasonCodeResponse
         * @description One NI-051 gate reason code, verbatim (code, severity, detail).
         */
        ReasonCodeResponse: {
            /** Code */
            code: string;
            /** Detail */
            detail: string;
            /**
             * Severity
             * @enum {string}
             */
            severity: "rejecting" | "limit" | "informational";
        };
        /**
         * ResolvedContext
         * @description Frozen chart inspection record (API_SPECIFICATION ``ResolvedContext``).
         *
         *     Contains the selected range (``selection.start``/``selection.end`` with the
         *     half-open UTC window rules of :class:`near_api.schemas.common.Selection`),
         *     the bounded registered filter dimensions as passed (the referenced chart
         *     definition controls the exact allowed values), the immutable pinned dataset version and the stable
         *     version identifiers whose ``context_hash`` binds them together. Server
         *     resolution/verification of every id happens where the context is created;
         *     this contract keeps a stored context from drifting afterwards.
         */
        ResolvedContext: {
            /**
             * Chart Definition Version Id
             * Format: uuid
             */
            chart_definition_version_id: string;
            /** Context Hash */
            context_hash: string;
            /**
             * Dataset Version Id
             * Format: uuid
             */
            dataset_version_id: string;
            /** Metric Definition Versions */
            metric_definition_versions: string[];
            /** Renderer Version */
            renderer_version: string;
            /**
             * Resolved At
             * Format: date-time
             */
            resolved_at: string;
            selection: components["schemas"]["ChartSelection"];
        };
        /**
         * ResolvedSelection
         * @description The resolved selection echoed back on series/chart-view responses.
         *
         *     Same window rules as the shared bootstrap ``Selection`` (ISO dates,
         *     frequency ``day``, non-empty half-open window of at most 366 days), but
         *     ``filters`` carries the chart-version-validated values instead of the
         *     strict-empty bootstrap object.
         */
        ResolvedSelection: {
            /**
             * End
             * Format: date
             */
            end: string;
            filters: components["schemas"]["ResolvedSelectionFilters"];
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
         * ResolvedSelectionFilters
         * @description Chart-version-validated filters carried inside a resolved selection.
         *
         *     Request filters arrive as the urlencoded ``filters`` query parameter and
         *     are validated server-side against the resolved chart definition version's
         *     closed ``filter_schema`` (the NI-031 versioned allowlist: string enums
         *     from approved source/recipient/price-basis mappings only; NI-071 adds
         *     list-valued multi-selections whose values fan out into one compared
         *     series per selected value). Unknown keys and unlisted values are rejected
         *     before any resolution happens, so this permissive container never
         *     serializes an unapproved filter value. The canonical serialized form of
         *     every value is a non-empty list of non-empty approved strings.
         */
        ResolvedSelectionFilters: {
            [key: string]: string[];
        };
        /** RichTextBoldMark */
        RichTextBoldMark: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "bold";
        };
        /** RichTextItalicMark */
        RichTextItalicMark: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "italic";
        };
        /**
         * RichTextLinkAttrs
         * @description Canonical link mark attributes. Scheme/credential rules for the target
         *     are enforced by the canonical rich text parser, which validates every body
         *     before these shapes are constructed.
         */
        RichTextLinkAttrs: {
            /** Href */
            href: string;
        };
        /** RichTextLinkMark */
        RichTextLinkMark: {
            attrs: components["schemas"]["RichTextLinkAttrs"];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "link";
        };
        /** RichTextList */
        RichTextList: {
            /** Content */
            content: components["schemas"]["RichTextListItem"][];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "bullet_list" | "ordered_list";
        };
        /** RichTextList */
        "RichTextList-Input": {
            /** Content */
            content: components["schemas"]["RichTextListItem-Input"][];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "bullet_list" | "ordered_list";
        };
        /** RichTextList */
        "RichTextList-Output": {
            /** Content */
            content: components["schemas"]["RichTextListItem-Output"][];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "bullet_list" | "ordered_list";
        };
        /**
         * RichTextListItem
         * @description One list item. The canonical parser enforces the ordering rule (a nested
         *     list must follow a paragraph) and the depth <= 3 bound before these shapes
         *     are constructed.
         */
        RichTextListItem: {
            /** Content */
            content: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList"])[];
            /**
             * Type
             * @constant
             */
            type: "list_item";
        };
        /**
         * RichTextListItem
         * @description One list item. The canonical parser enforces the ordering rule (a nested
         *     list must follow a paragraph) and the depth <= 3 bound before these shapes
         *     are constructed.
         */
        "RichTextListItem-Input": {
            /** Content */
            content: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList-Input"])[];
            /**
             * Type
             * @constant
             */
            type: "list_item";
        };
        /**
         * RichTextListItem
         * @description One list item. The canonical parser enforces the ordering rule (a nested
         *     list must follow a paragraph) and the depth <= 3 bound before these shapes
         *     are constructed.
         */
        "RichTextListItem-Output": {
            /** Content */
            content: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList-Output"])[];
            /**
             * Type
             * @constant
             */
            type: "list_item";
        };
        /** RichTextParagraph */
        RichTextParagraph: {
            /** Content */
            content: components["schemas"]["RichTextRun"][];
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "paragraph";
        };
        /**
         * RichTextRun
         * @description One text node with its (bounded, deduplicated) inline marks.
         */
        RichTextRun: {
            /**
             * Marks
             * @default []
             */
            marks: (components["schemas"]["RichTextBoldMark"] | components["schemas"]["RichTextItalicMark"] | components["schemas"]["RichTextLinkMark"])[];
            /** Text */
            text: string;
            /**
             * Type
             * @constant
             */
            type: "text";
        };
        /**
         * RiskInput
         * @description Canonical risk node contract (EDITOR_SPECIFICATION ``risk`` row).
         *
         *     An explicit counterargument card: ``title`` + bounded rich text ``body``
         *     with an optional same-document hypothesis link. There is deliberately no
         *     algorithmic probability score field. No convenience REST route is
         *     specified for risk blocks; risk nodes are edited through the document
         *     revision flow (NI-039/NI-040), so this contract serves the editor, the
         *     projections and the export path.
         */
        RiskInput: {
            /**
             * Block Id
             * Format: uuid
             */
            block_id: string;
            /** Body */
            body: (components["schemas"]["RichTextParagraph"] | components["schemas"]["RichTextList"])[];
            /** Related Hypothesis Id */
            related_hypothesis_id?: string | null;
            /** Title */
            title: string;
        };
        /**
         * RunSampleResponse
         * @description The published sample window and size (half-open, gate-exact).
         */
        RunSampleResponse: {
            /** End Exclusive */
            end_exclusive: string;
            /** Nobs */
            nobs: number;
            /** Start */
            start: string;
        };
        /**
         * SavedChartCreateRequest
         * @description POST /saved-charts body (API_SPECIFICATION row, no owner field).
         */
        SavedChartCreateRequest: {
            /**
             * Chart Definition Version Id
             * Format: uuid
             */
            chart_definition_version_id: string;
            /**
             * Dataset Version Id
             * Format: uuid
             */
            dataset_version_id: string;
            /** Label */
            label?: string | null;
            /**
             * Mode
             * @enum {string}
             */
            mode: "live" | "snapshot";
            selection: components["schemas"]["SavedChartSelectionInput"];
            /** Snapshot Id */
            snapshot_id?: string | null;
        };
        /**
         * SavedChartDetailResponse
         * @description GET /saved-charts/{id}: the owned instance plus its resolved view.
         *
         *     ``view`` is the standard public ``ChartView`` resolved through the shared
         *     NI-032 delivery service — for ``live`` mode against the latest approved
         *     dataset at read time, so live updates are labeled by the view's own
         *     dataset identity and ``last_resolved_dataset_version_id``.
         */
        SavedChartDetailResponse: {
            /** Dataset Changed */
            dataset_changed: boolean;
            saved_chart: components["schemas"]["SavedChartResponse"];
            view: components["schemas"]["ChartViewResponse"];
        };
        /**
         * SavedChartListResponse
         * @description Owner-scoped saved-chart list (bounded opaque offset cursor).
         */
        SavedChartListResponse: {
            /** Items */
            items: components["schemas"]["SavedChartResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /**
         * SavedChartResponse
         * @description One owned saved chart instance (API_SPECIFICATION ``SavedChart``).
         */
        SavedChartResponse: {
            /**
             * Chart Definition Version Id
             * Format: uuid
             */
            chart_definition_version_id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Label */
            label: string | null;
            /** Last Resolved Dataset Version Id */
            last_resolved_dataset_version_id: string | null;
            /**
             * Mode
             * @enum {string}
             */
            mode: "live" | "snapshot";
            selection: components["schemas"]["SavedChartSelectionInput"];
            /** Snapshot Id */
            snapshot_id: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * SavedChartSelectionInput
         * @description Create-time canonical selection (half-open window rules inherited).
         */
        SavedChartSelectionInput: {
            /**
             * End
             * Format: date
             */
            end: string;
            /** Filters */
            filters: {
                [key: string]: string[];
            };
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
         * SavedChartUpdateRequest
         * @description Explicit contextual edits; absence retains a field, label null clears it.
         */
        SavedChartUpdateRequest: {
            /** Dataset Version Id */
            dataset_version_id?: string | null;
            /** Label */
            label?: string | null;
            /** Mode */
            mode?: ("live" | "snapshot") | null;
            selection?: components["schemas"]["SavedChartSelectionInput"] | null;
            /** Snapshot Id */
            snapshot_id?: string | null;
        };
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
        /**
         * SeriesResponse
         * @description One metric's resolved series (API_SPECIFICATION ``Series``).
         *
         *     ``points`` carry explicit nulls with gap reasons; a point's null value is
         *     never converted to zero and every point keeps its UTC half-open interval,
         *     quality status, bound kind and reasons.
         */
        SeriesResponse: {
            dataset: components["schemas"]["DatasetResponse"];
            metric: components["schemas"]["MetricResponse"];
            /** Points */
            points: components["schemas"]["Observation"][];
            selection: components["schemas"]["ResolvedSelection"];
            /** Sources */
            sources: components["schemas"]["DataSourceResponse"][];
        };
        /**
         * TolerancesResponse
         * @description The declared reproduction tolerances of a published fit.
         */
        TolerancesResponse: {
            /** Coefficient Atol */
            coefficient_atol: string;
            /** Coefficient Rtol */
            coefficient_rtol: string;
        };
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
        /**
         * VersionListResponse
         * @description GET /documents/{id}/versions response: bounded page, newest first.
         */
        VersionListResponse: {
            /** Items */
            items: components["schemas"]["VersionSummaryResponse"][];
            /** Next Cursor */
            next_cursor: string | null;
        };
        /** VersionSummaryResponse */
        VersionSummaryResponse: {
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
    listCharts: {
        parameters: {
            query?: {
                q?: string | null;
                category?: string | null;
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["ChartListResponse"];
                };
            };
            /** @description Request failed validation */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getChart: {
        parameters: {
            query?: {
                version?: number | null;
            };
            header?: never;
            path: {
                chart_id: string;
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
                    "application/json": components["schemas"]["ChartDefinitionResponse"];
                };
            };
            /** @description Chart definition not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    getChartView: {
        parameters: {
            query: {
                definition_version: number;
                start: string;
                end: string;
                dataset_version?: string;
                frequency?: string;
                filters?: string | null;
            };
            header?: never;
            path: {
                chart_id: string;
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
                    "application/json": components["schemas"]["ChartViewResponse"];
                };
            };
            /** @description Chart or dataset not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Range, filter or reference invalid */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No approved dataset exists for latest */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    listDataSources: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["DataSourceListResponse"];
                };
            };
            /** @description Request failed validation */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getDataSource: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: string;
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
                    "application/json": components["schemas"]["DataSourceResponse"];
                };
            };
            /** @description Data source not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    getDataset: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                version_id: string;
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
                    "application/json": components["schemas"]["DatasetResponse"];
                };
            };
            /** @description Approved dataset version not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    getDatasetManifest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                version_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Sanitized prepared manifest JSON */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Approved version or servable manifest not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Manifest exceeds the bounded public payload size */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
                "idempotency-key"?: string | null;
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    deleteDocument: {
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
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    renameDocument: {
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
                "application/json": components["schemas"]["DocumentRenameRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DocumentSummary"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    addChartBlock: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChartBlockInsertRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChartBlockMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    getDocumentChartView: {
        parameters: {
            query: {
                chart_definition_version_id: string;
                start: string;
                end: string;
                dataset_version: string;
                filters?: string | null;
            };
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
                    "application/json": components["schemas"]["DocumentChartViewResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
            /** @description Approved chart data is unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    listDocumentEvidence: {
        parameters: {
            query?: {
                hypothesis_id?: string | null;
                version_id?: string | null;
            };
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
                    "application/json": components["schemas"]["Evidence"][];
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
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createDocumentEvidence: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EvidenceCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    listDocumentEvidenceTargets: {
        parameters: {
            query: {
                target_kind: "model_run" | "citation";
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["EvidenceTargetListResponse"];
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
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    deleteDocumentEvidence: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
                evidence_id: string;
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
                    "application/json": components["schemas"]["EvidenceDeleteResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    updateDocumentEvidence: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
                evidence_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EvidencePatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EvidenceMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    createDocumentExport: {
        parameters: {
            query?: never;
            header?: {
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DocumentExportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportJobResponse"];
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
            /** @description Export is not downloadable in its current lifecycle state, or the Idempotency-Key was reused with a different request */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The export artifact has expired */
            410: {
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
        };
    };
    getDocumentExport: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                document_id: string;
                job_id: string;
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
                    "application/json": components["schemas"]["ExportJobResponse"];
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
            /** @description Export is not downloadable in its current lifecycle state, or the Idempotency-Key was reused with a different request */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The export artifact has expired */
            410: {
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
        };
    };
    downloadDocumentExport: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                document_id: string;
                job_id: string;
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
                    "application/json": unknown;
                    "application/zip": string;
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
            /** @description Export is not downloadable in its current lifecycle state, or the Idempotency-Key was reused with a different request */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description The export artifact has expired */
            410: {
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
        };
    };
    listDocumentHypotheses: {
        parameters: {
            query?: {
                version_id?: string | null;
            };
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
                    "application/json": components["schemas"]["Hypothesis"][];
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
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createDocumentHypothesis: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HypothesisCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HypothesisMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    deleteDocumentHypothesis: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
                hypothesis_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HypothesisDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HypothesisDeleteResponse"];
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
            /** @description Revision, idempotency or linked-reference conflict */
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
    updateDocumentHypothesis: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
                hypothesis_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["HypothesisPatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HypothesisMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    listDocumentInsights: {
        parameters: {
            query?: {
                version_id?: string | null;
            };
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
                    "application/json": components["schemas"]["Insight"][];
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
            /** @description Request failed validation or references an unavailable target */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
        };
    };
    createDocumentInsight: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InsightCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InsightMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    deleteDocumentInsight: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
                insight_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InsightDeleteRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InsightDeleteResponse"];
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
            /** @description Revision, idempotency or linked-evidence conflict */
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
    updateDocumentInsight: {
        parameters: {
            query?: never;
            header?: {
                "if-match"?: string | null;
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path: {
                document_id: string;
                insight_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InsightPatchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InsightMutationResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    listDocumentVersions: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["VersionListResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
                "idempotency-key"?: string | null;
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    getDocumentVersion: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                document_id: string;
                version_id: string;
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
                    "application/json": components["schemas"]["VersionDetailResponse"];
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
            /** @description Revision conflict (document moved) or Idempotency-Key reused with a different request */
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
    getDocumentVersionChartCsv: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                document_id: string;
                version_id: string;
                block_id: string;
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
                    "text/csv": string;
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
            /** @description Frozen chart evidence could not be reconstructed */
            409: {
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
        };
    };
    getDocumentVersionChartView: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                document_id: string;
                version_id: string;
                block_id: string;
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
                    "application/json": components["schemas"]["ChartViewResponse"];
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
            /** @description Frozen chart evidence could not be reconstructed */
            409: {
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
    listMetrics: {
        parameters: {
            query?: {
                availability?: string | null;
                category?: string | null;
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["MetricListResponse"];
                };
            };
            /** @description Request failed validation */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getMetric: {
        parameters: {
            query?: {
                version?: number | null;
            };
            header?: never;
            path: {
                metric_id: string;
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
                    "application/json": components["schemas"]["MetricResponse"];
                };
            };
            /** @description Metric definition not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    getMetricSeries: {
        parameters: {
            query: {
                definition_version: number;
                start: string;
                end: string;
                dataset_version?: string;
                frequency?: string;
                filters?: string | null;
            };
            header?: never;
            path: {
                metric_id: string;
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
                    "application/json": components["schemas"]["SeriesResponse"];
                };
            };
            /** @description Metric or dataset not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Range, filter or reference invalid */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description No approved dataset exists for latest */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    listModelDefinitions: {
        parameters: {
            query?: {
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["ModelDefinitionListResponse"];
                };
            };
            /** @description Request failed validation */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getModelDefinition: {
        parameters: {
            query?: {
                version?: number | null;
            };
            header?: never;
            path: {
                model_id: string;
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
                    "application/json": components["schemas"]["ModelDefinitionResponse"];
                };
            };
            /** @description Published model definition not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    getModelReadiness: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                model_id: string;
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
                    "application/json": components["schemas"]["ModelReadinessResponse"];
                };
            };
            /** @description No published readiness verdict */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    listModelRuns: {
        parameters: {
            query?: {
                model_id?: string | null;
                cursor?: string | null;
                limit?: number | null;
            };
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
                    "application/json": components["schemas"]["ModelRunListResponse"];
                };
            };
            /** @description Request failed validation */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    getModelRun: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
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
                    "application/json": components["schemas"]["ModelRunDetailResponse"];
                };
            };
            /** @description Published run not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    getModelRunManifest: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Canonical manifest bundle JSON */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Published run not found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
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
    listSavedCharts: {
        parameters: {
            query?: {
                q?: string | null;
                category?: string | null;
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
                    "application/json": components["schemas"]["SavedChartListResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
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
    createSavedChart: {
        parameters: {
            query?: never;
            header?: {
                "idempotency-key"?: string | null;
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SavedChartCreateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedChartResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
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
    getSavedChart: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                instance_id: string;
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
                    "application/json": components["schemas"]["SavedChartDetailResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
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
    deleteSavedChart: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                instance_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
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
    updateSavedChart: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                instance_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SavedChartUpdateRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SavedChartResponse"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorResponse"];
                };
            };
            /** @description Service Unavailable */
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
