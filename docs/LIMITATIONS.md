# Known Limitations & Responsible Disclosures

In accordance with Hackathon Round 2 standards, BrandGuard provides clear and honest disclosures regarding its current architectural boundaries, performance envelope, and security controls.

---

## 1. Scope Boundaries (Round 2 Build)

1. **No Automated Publishing**:
   - BrandGuard does not auto-publish to CMS systems, social media APIs, or advertising platforms.
   - All content publishing requires an authorized human manager or reviewer sign-off.
2. **Text-Only Extraction for Document Uploads**:
   - Uploaded PDF and Word (.docx) files are converted into plain text streams for review.
   - Spatial layout inspection, page-coordinate bounding boxes, and column-aware formatting are out of scope for Round 2 and scheduled for Round 3.
3. **No Image Pixel or Logo Contrast Review**:
   - Image files (.png, .jpeg) are registered as brand assets but are not analyzed at the raw pixel level.
   - Text accessibility checks verify markup-level attributes (empty alt attributes on `<img>` tags and vague link text like `[click here]`). Image color contrast and visual logo clear-space inspection are scheduled for Round 3.
4. **No Real-Time Collaborative Co-Editing**:
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
