# Known Limitations & Responsible Disclosures (Round 3)

In accordance with Hackathon Round 3 standards, BrandGuard provides clear and honest disclosures regarding its current architectural boundaries, performance envelope, and security controls.

---

## 1. Scope Boundaries

1. **No Automated Publishing**:
   - BrandGuard does not auto-publish to CMS systems, social media APIs, or advertising platforms.
   - All content publishing requires an authorized human manager or reviewer sign-off.
2. **DOCX and Complex PDF Layouts**:
   - DOCX content is extracted as text. PDF findings include page and line bounding boxes, but complex columns, rotated text, and decorative typography may not align perfectly with a highlight.
3. **Image Inspection Depends on Source Records and Instance Memory**:
   - PNG, JPEG, and SVG review uses RapidOCR/ONNX, with a 12-megapixel dimension cap. It is disabled by default; set `IMAGE_REVIEW_ENABLED=true` only on an instance with enough memory. The measured full-app + OCR + OpenCV peak on the development machine was about 611 MB, above the 450 MB target and the Render free-tier 512 MB limit, so leave it disabled on Render free.
   - Palette checks need RGB/HEX values in approved asset metadata. Logo clear-space checks need a readable approved logo file and an explicit measurable minimum in a guideline. OCR may miss or misread stylized text; contrast checks cover detected word regions only. EXIF/IPTC metadata is not read.
4. **Single-Brand Workspace Scope**:
   - The current data model has no separate team entity. Repeated-dispute suppression and feedback statistics therefore use the database's single brand workspace.
5. **LLM-Generated Guideline Revisions**:
   - Proposed wording is generated only when a live LLM provider is configured. Offline mock mode does not create draft revisions.
6. **Process-Local Rate Limits**:
   - API request counters are held in each application process. Deployments with multiple workers or replicas do not share quotas.
7. **No Real-Time Collaborative Co-Editing**:
   - Content is governed through distinct revisions (`v1 -> v2 -> v3`), structured comments, and diff-based decisions rather than multi-cursor live editing.

---

## 2. Infrastructure & Hosting Characteristics

1. **Render Free Tier Cold Starts**:
   - The application runs on a free Render container (512 MB RAM, 0.1 CPU). When idle for more than 15 minutes, the container sleeps and takes approximately 40-50 seconds to wake on the initial incoming request.
   - The frontend includes a responsive notification banner (`ColdStartBanner`) informing users during cold starts to prevent confusion.
2. **Disposable Ephemeral Container Storage**:
   - Render's container disk is ephemeral. The local ChromaDB vector directory (`/tmp/chroma`) is disposable.
   - **PostgreSQL is the sole source of truth**: on every application boot, BrandGuard automatically inspects ChromaDB and re-indexes all approved guidelines, facts, and terms from PostgreSQL if the vector collection is empty.
3. **Word & Document Limits**:
   - Content uploads are capped at 5 MB per document.
   - Text evaluation is capped at approximately 5,000 words per single check to ensure responsive performance within the 512 MB memory budget.

---

## 3. Honest Security & Privacy Disclosures

1. **Encryption**:
   - **In-Transit**: Encrypted via HTTPS / TLS 1.3 terminated at Render's edge load balancer.
   - **At-Rest**: Managed and encrypted at rest by Neon's serverless AWS storage layer. BrandGuard does not implement proprietary disk-level encryption.
2. **Authentication & Password Protection**:
   - Passwords are salted and hashed using standard `bcrypt`.
   - API authentication uses stateless JSON Web Tokens (JWT) signed with `HS256` and an 8-hour expiration window.
3. **Excerpt-Only Data Transmission**:
   - When external LLMs (such as Anthropic Claude) are enabled, BrandGuard never transmits whole document libraries. It transmits only the specific text span under evaluation and the top-k retrieved source snippets.
4. **Prompt Injection Defense**:
   - All user-supplied text sent to reasoning engines is encapsulated in explicit boundary tags (`--- BEGIN UNTRUSTED CONTENT ---`) with system prompt directives instructing the model never to execute embedded commands.
