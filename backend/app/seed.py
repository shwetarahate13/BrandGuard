"""Seed data generator for BrandGuard.

Seeds fictional brand 'Aurelia Foods':
- Guidelines (tone, claims, terminology, accessibility, approvals)
- 25+ approved facts (including expired facts to test outdated info detection)
- Approved terms (preferred vs avoid)
- Brand assets
- Demo users (Creator, Manager, Reviewer, Admin)
- 8-10 sample submissions with planted errors and realistic review history
"""
from datetime import datetime, timezone, timedelta
import logging
from pathlib import Path
from sqlalchemy.orm import Session

from backend.app.models.models import (
    User, UserRole, GuidelineDoc, GuidelineClause, ApprovedFact, Term, Asset, AssetKind,
    Submission, SubmissionVersion, SubmissionStatus, ContentType,
    Finding, FindingCategory, FindingSeverity, FindingConfidence, FindingStatus, SourceType,
    Decision, DecisionAction, Comment, Approval, ApprovalDecision
)
from backend.app.services.auth import hash_password, verify_password

logger = logging.getLogger(__name__)

DEMO_USERS = (
    ("Janvi Thakre", "creator@nexora.dev", "CreatorDemo2026!", UserRole.creator),
    ("Shweta Rahate", "manager@nexora.dev", "ManagerDemo2026!", UserRole.manager),
    ("Elena Rostova", "reviewer@nexora.dev", "ReviewerDemo2026!", UserRole.reviewer),
    ("Admin Nexora", "admin@nexora.dev", "AdminDemo2026!", UserRole.admin),
)


def ensure_demo_users(db: Session) -> dict[str, User]:
    """Create or synchronize the four throwaway accounts shown on the demo login page."""
    user_map: dict[str, User] = {}
    for name, email, password, role in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                name=name,
                email=email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(user)
            db.flush()
        else:
            # Demo mode intentionally keeps these shared throwaway credentials aligned
            # with the login page, even when the database predates the current seed.
            if not verify_password(password, user.password_hash):
                user.password_hash = hash_password(password)
            user.role = role
            user.is_active = True
        user_map[role.value] = user
    return user_map


def run_seed(db: Session):
    """Idempotently seed the BrandGuard database."""
    logger.info("Executing BrandGuard database seed...")

    # 1. Demo Users
    user_map = ensure_demo_users(db)

    creator_u = user_map.get("creator")
    manager_u = user_map.get("manager")
    reviewer_u = user_map.get("reviewer")

    # 2. Guidelines for Aurelia Foods
    existing_doc = db.query(GuidelineDoc).filter(GuidelineDoc.title == "Aurelia Foods Brand Guidelines").first()
    if not existing_doc:
        doc = GuidelineDoc(
            title="Aurelia Foods Brand Guidelines",
            description="Comprehensive brand governance: voice, tone, claims substantiation, terminology, and accessibility.",
        )
        db.add(doc)
        db.flush()

        clauses_data = [
            ("VOICE-1", "Brand Voice & Tone",
             "Aurelia Foods speaks with a warm, grounded, authentic, and culinary-literate tone. We communicate like passionate food artisans sharing knowledge with our community. Avoid marketing hyperbole, aggressive hype, Internet slang ('gonna', 'super cool', 'dope'), ALL-CAPS words, and multiple exclamation marks."),
            ("CLAIM-1", "Claims Substantiation & Superlatives",
             "All nutritional, health, and sourcing claims must be backed by approved clinical testing or certified records. Never use unprovable superlatives ('world's best', '#1', 'unbeatable', 'miracle', 'revolutionary') or absolute guarantees ('guaranteed', '100% safe', 'cures', 'risk-free')."),
            ("CLAIM-2", "Organic & Dietary Certifications",
             "Only products holding current USDA Organic certification or non-GMO Project verification may be described as 'certified organic'. General terms like 'all-natural' must be clearly qualified with specific ingredients."),
            ("TERM-1", "Product & Brand Naming",
             "Always use our official product designations: 'Aurelia Artisan Pantry', 'Golden Oat Elixir', and 'Heritage Sourdough'. Refer to our customers as 'patrons' or 'community members', never 'users' or 'consumers'. Refer to our production spaces as 'artisan kitchens', never 'factories' or 'plants'."),
            ("A11Y-1", "Content Accessibility",
             "All promotional text must be accessible. Provide descriptive link text instead of vague phrases like 'click here' or 'read more'. Avoid long all-caps text blocks. Keep sentence structure concise, aiming for an average reading level below Grade 12."),
            ("LEGAL-1", "Required Health Disclaimers",
             "Any copy discussing wellness benefits, adaptogens, or digestive wellness must include the standard FDA disclaimer: 'These statements have not been evaluated by the Food and Drug Administration. This product is not intended to diagnose, treat, cure, or prevent any disease.'"),
            ("STYLE-1", "Spelling & Grammar",
             "Content must be free of spelling and grammar errors. Use clear, correct English while preserving the creator's stated intent."),
        ]

        clause_objs = {}
        for idx, (code, title, text) in enumerate(clauses_data):
            c = GuidelineClause(
                doc_id=doc.id,
                code=code,
                title=title,
                text=text,
                order_index=idx,
            )
            db.add(c)
            db.flush()
            clause_objs[code] = c
    else:
        clause_objs = {c.code: c for c in existing_doc.clauses}
        if "STYLE-1" not in clause_objs:
            style_clause = GuidelineClause(
                doc_id=existing_doc.id,
                code="STYLE-1",
                title="Spelling & Grammar",
                text="Content must be free of spelling and grammar errors. Use clear, correct English while preserving the creator's stated intent.",
                order_index=len(clause_objs),
            )
            db.add(style_clause)
            db.flush()
            clause_objs["STYLE-1"] = style_clause

    # 3. Approved Facts (25+ facts, including expired ones)
    now = datetime.now(timezone.utc)
    expired_2022 = datetime(2022, 12, 31, tzinfo=timezone.utc)
    expired_2023 = datetime(2023, 12, 31, tzinfo=timezone.utc)
    valid_future = datetime(2028, 12, 31, tzinfo=timezone.utc)

    facts_data = [
        ("Aurelia Foods was founded in 2021 in Portland, Oregon by culinary artisans.", "Corporate Charter 2021", None, valid_future),
        ("Golden Oat Elixir contains 100% certified organic gluten-free oats grown in Willamette Valley.", "USDA Organic Cert #98214", None, valid_future),
        ("The Artisan Pantry Subscription box is priced at $34 per month including shipping.", "Pricing Schedule Q1 2024", datetime(2024, 1, 1, tzinfo=timezone.utc), valid_future),
        ("The introductory pantry box cost was $28 per month.", "Legacy 2022 Pricing (SUPERSEDED)", datetime(2022, 1, 1, tzinfo=timezone.utc), expired_2023), # EXPIRED FACT
        ("Aurelia Foods donates 15% of annual net profits to local regenerative agriculture farms.", "Corporate Impact Report 2023", None, valid_future),
        ("In 2022, renewable energy powering the Portland kitchen was 50%.", "2022 Sustainability Audit (SUPERSEDED)", datetime(2022, 1, 1, tzinfo=timezone.utc), expired_2022), # EXPIRED FACT
        ("As of 2024, 85% of our Portland kitchen electricity is generated by on-site solar arrays.", "2024 Green Energy Audit", datetime(2024, 1, 1, tzinfo=timezone.utc), valid_future),
        ("Heritage Sourdough Starter has been continuously maintained with wild yeasts since 1998.", "Master Baker Provenance Log", None, valid_future),
        ("Aurelia Foods distributes to over 450 independent grocery stores across the Pacific Northwest.", "Q3 2024 Retail Distribution Report", None, valid_future),
        ("In 2022, distribution was limited to 120 regional specialty grocers.", "2022 Distribution Log (SUPERSEDED)", datetime(2022, 1, 1, tzinfo=timezone.utc), expired_2022), # EXPIRED FACT
        ("All packaging materials are 100% compostable or made from post-consumer recycled cardboard.", "Packaging Materials Certification", None, valid_future),
        ("Stone-Ground Einkorn Flour is sourced exclusively from certified organic family farms in Idaho.", "Supplier Contract #FL-402", None, valid_future),
        ("Fermentation of Heritage Sourdough occurs over a 36-hour cold-ferment cycle.", "Kitchen Standard Operating Procedure #201", None, valid_future),
        ("Golden Oat Elixir contains zero added artificial sugars or gums.", "Laboratory Nutrition Assay 2024", None, valid_future),
        ("Aurelia Foods products are kosher certified by Oregon Kosher.", "Oregon Kosher Certificate 2024", None, valid_future),
        ("All shipments are carbon-neutral offset via NativeEnergy reforestation credits.", "NativeEnergy Partnership #NE-882", None, valid_future),
        ("Aurelia Foods employs 42 full-time team members with living wage and healthcare benefits.", "HR Audit June 2024", None, valid_future),
        ("Our culinary director holds an Advanced Diploma from the Culinary Institute of America.", "Executive Credentials", None, valid_future),
        ("Wildflower Honey Infusion uses raw unfiltered wildflower honey from Willamette Valley apiaries.", "Oregon Apiary Certificate #H-110", None, valid_future),
        ("No Aurelia Foods product uses artificial emulsifiers, carrageenan, or polysorbates.", "Ingredient Formulation Standard #04", None, valid_future),
        ("Customer service inquiries receive personal email responses within 2 business hours.", "CS Service Level Agreement", None, valid_future),
        ("Cold-Pressed Sunflower Oil is expeller-pressed below 110 degrees Fahrenheit.", "Processing Verification Sheet", None, valid_future),
        ("Sea salt used in all savory pantry products is hand-harvested Netarts Bay sea salt.", "Jacobsen Salt Co. Partnership Memo", None, valid_future),
        ("Aurelia Foods has an A+ rating from the Pacific Northwest Good Food Alliance.", "Alliance Annual Review 2024", None, valid_future),
        ("All gluten-free products undergo ELISA batch testing verifying less than 5 ppm gluten.", "Food Allergy Laboratory Batch Reports", None, valid_future),
        ("Aurelia Foods ships across all 50 US states via climate-controlled eco-carriers.", "Logistics Directory 2024", None, valid_future),
    ]
    structured_fact_data = {
        "The Artisan Pantry Subscription box is priced at $34 per month including shipping.": (
            "Artisan Pantry Subscription box", "$34", "per month",
        ),
        "The introductory pantry box cost was $28 per month.": (
            "Artisan Pantry Subscription box", "$28", "per month",
        ),
        "In 2022, renewable energy powering the Portland kitchen was 50%.": (
            "Portland kitchen", "50%", "solar electricity",
        ),
        "As of 2024, 85% of our Portland kitchen electricity is generated by on-site solar arrays.": (
            "Portland kitchen", "85%", "solar electricity",
        ),
    }

    fact_objs = []
    if db.query(ApprovedFact).count() == 0:
        for stmt, note, v_from, v_to in facts_data:
            subject, value, unit = structured_fact_data.get(stmt, (None, None, None))
            f = ApprovedFact(
                statement=stmt,
                subject=subject,
                value=value,
                unit=unit,
                source_note=note,
                valid_from=v_from,
                valid_to=v_to,
            )
            db.add(f)
            fact_objs.append(f)
        db.flush()
    else:
        for fact in db.query(ApprovedFact).filter(ApprovedFact.statement.in_(structured_fact_data)).all():
            if fact.subject is None:
                fact.subject, fact.value, fact.unit = structured_fact_data[fact.statement]
        db.flush()

    # 4. Approved Terms
    terms_data = [
        ("Aurelia Artisan Pantry", ["Aurelia Pantry", "Aurelia Foods Pantry", "the pantry brand"], "Official brand product line"),
        ("patrons", ["users", "consumers", "clients", "buyers"], "Brand community language"),
        ("artisan kitchens", ["factories", "manufacturing plants", "industrial plant"], "Brand production facility terminology"),
        ("accessible pricing", ["cheap", "budget-grade", "low cost"], "Pricing positioning"),
        ("crafted", ["mass produced", "manufactured"], "Production verb"),
        ("sustainable", ["eco-friendly", "green"], "Specific sustainability claims preferred"),
    ]

    term_objs = {}
    if db.query(Term).count() == 0:
        for pref, avoid, note in terms_data:
            t = Term(preferred=pref, avoid=avoid, note=note)
            db.add(t)
            db.flush()
            term_objs[pref] = t

    # 5. Assets
    if db.query(Asset).count() == 0:
        db.add(Asset(name="Aurelia Foods Primary Logo", kind=AssetKind.logo, file_path="/assets/aurelia_logo.svg"))
        db.add(Asset(name="Golden Oat Elixir Product Shot", kind=AssetKind.image, file_path="/assets/golden_oat.png"))
        db.add(Asset(name="Heritage Sourdough Packaging Template", kind=AssetKind.template, file_path="/assets/sourdough_pkg.pdf"))
        db.flush()

    # 6. Sample Submissions with Planted Errors
    if creator_u:
        samples = [
            # 1. Unsupported promotional claims + forbidden superlatives
            {
                "title": "Fall Season Golden Oat Elixir Campaign",
                "intent": "Announce the seasonal release of Golden Oat Elixir and highlight its organic quality and health benefits.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.checked,
                "text": "Golden Oat Elixir is the world's best oat beverage, clinically proven to boost vitality and guaranteed to rejuvenate your morning routine. Our revolutionary formula cures morning fatigue with 100% safe organic ingredients. Order yours today!",
            },
            # 2. Outdated statistics ($28 legacy price, 50% solar)
            {
                "title": "2024 Sustainability & Pricing Update",
                "intent": "Inform patrons about subscription pricing and our solar energy milestones.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.checked,
                "text": "The Artisan Pantry Subscription box costs $28 per month. Our Portland kitchen currently runs on 50% solar energy as we continue reducing emissions.",
            },
            # 3. Off-brand tone and ALL-CAPS
            {
                "title": "Weekend Harvest Sale Announcement",
                "intent": "Invite our community to visit the weekend artisan tasting event.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.checked,
                "text": "Hey guys! We are gonna throw a super cool party this weekend. BUY NOW AND GET FREE SHIPPING on all orders! You will totally love these crazy good snacks.",
            },
            # 4. Banned terminology ('cheap', 'users', 'factories')
            {
                "title": "Behind the Scenes: Sourdough Craftsmanship",
                "intent": "Showcase our traditional baking process to prospective patrons.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.checked,
                "text": "Our cheap sourdough loaves offer great taste for our users. Every loaf is baked in our modern factories using traditional wild yeast starters.",
            },
            # 5. Accessibility violations (vague links, missing alt text, long sentence)
            {
                "title": "New Community Journal Entry #12",
                "intent": "Share sourdough recipe guide and seasonal pantry pairing ideas.",
                "content_type": ContentType.markdown,
                "status": SubmissionStatus.checked,
                "text": "Explore our harvest sourdough pairings! [click here](https://aureliafoods.com/recipes) to view the recipe.\n\n![](https://aureliafoods.com/images/loaf.jpg)\n\nWe carefully handcraft each loaf utilizing stone-ground einkorn flour alongside netarts bay sea salt and pure spring water followed by a rigorous cold-fermentation cycle spanning thirty-six hours before transferring each batch to stone-hearth ovens operated by master artisans who have perfected baking over decades of dedication.",
            },
            # 6. Perfectly clean piece (proves NO over-flagging)
            {
                "title": "A Note on Our Autumn Einkorn Harvest",
                "intent": "Explain our seasonal grain sourcing and celebrate local farming partnerships.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.approved,
                "text": "Stone-Ground Einkorn Flour is sourced exclusively from certified organic family farms in Idaho. Aurelia Foods distributes to over 450 independent grocery stores across the Pacific Northwest. We thank our patrons for supporting sustainable regional agriculture.",
            },
            # 7. Ambiguous claim requiring human reviewer routing
            {
                "title": "Artisan Botanical Tea Infusion Launch",
                "intent": "Introduce a new herbal botanical blend made with regional wildflowers.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.in_review,
                "text": "Our new Wildflower Honey Infusion is crafted with all-natural botanical botanicals harvested from Willamette Valley apiaries. Experience pure botanical tranquility in every cup.",
                "review_finding": {
                    "id": "demo-finding-botanical-claim",
                    "clause": "CLAIM-1",
                    "match": "pure botanical tranquility",
                    "issue": "This wellness benefit needs a supporting approved fact and reviewer verification.",
                    "category": FindingCategory.unsupported_claim,
                    "location": None,
                },
            },
            # 8. Finished workflow: Changes requested and resolved
            {
                "title": "Holiday Gift Box Press Release",
                "intent": "Announce holiday gift box bundles to regional food media.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.changes_requested,
                "text": "The Aurelia Artisan Pantry gift collection is available now. Experience the finest artisan pantry foods crafted with netarts bay sea salt.",
            },
            {
                "id": "demo-submission-draft-weekend-market",
                "title": "DEMO · Weekend Farm Market Invitation",
                "intent": "Invite patrons to a seasonal tasting at the Portland artisan kitchen.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.draft,
                "text": "Hey guys, we're gonna have the best tasting ever!!! Come hang with us this Saturday.",
            },
            {
                "id": "demo-submission-checked-health-claim",
                "title": "DEMO · Golden Oat Elixir Product Banner",
                "intent": "Introduce the oat drink with a concise product benefit.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.checked,
                "text": "Clinically proven to cure fatigue. This drink is 100% safe for everyone and is number one in America.",
            },
            {
                "id": "demo-submission-review-sustainability",
                "title": "DEMO · Spring Sustainability Newsletter",
                "intent": "Share a current energy and packaging update with the community.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.in_review,
                "text": "Our artisan kitchens now use 50% solar energy, and 96% of patrons choose our new packaging.",
                "review_finding": {
                    "id": "demo-finding-sustainability-stat",
                    "fact_statement": "As of 2024, 85% of our Portland kitchen electricity is generated by on-site solar arrays.",
                    "match": "50% solar energy",
                    "issue": "Your text vs approved value — your text: '50%'; approved value: '85% solar electricity'. Source: 2024 Green Energy Audit.",
                    "category": FindingCategory.factual_accuracy,
                    "suggested_rewrite": "85% solar energy",
                    "location": None,
                },
            },
            {
                "id": "demo-submission-rejected-guarantee",
                "title": "DEMO · Guaranteed Wellness Display Ad",
                "intent": "Promote a pantry product at a weekend market.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.rejected,
                "text": "Our miracle blend is guaranteed to cure digestion problems and is 100% safe for every patron.",
            },
            {
                "id": "demo-submission-image-review",
                "title": "DEMO · Harvest Pantry Image Proof",
                "intent": "Review the promotional image for unsupported copy and accessible contrast.",
                "content_type": ContentType.image,
                "status": SubmissionStatus.checked,
                "text": "Guaranteed to cure fatigue. 100% safe for everyone! The world's best loaf. CLICK HERE",
                "source_filename": "campaign-image.png",
                "source_mime_type": "image/png",
                "source_path": "samples/campaign-image.png",
                "source_layout": {"media": "image", "width": 1200, "height": 675, "regions": []},
                "review_finding": {
                    "id": "demo-finding-image-claim",
                    "clause": "CLAIM-1",
                    "match": "Guaranteed to cure fatigue",
                    "issue": "Absolute safety claim in the promotional image requires substantiation.",
                    "category": FindingCategory.unsupported_claim,
                    "location": {"page": 1, "bbox": [112, 316, 522, 362], "media": "image"},
                },
            },
            {
                "id": "demo-submission-pdf-review",
                "title": "DEMO · Spring Campaign PDF Proof",
                "intent": "Inspect the campaign proof and confirm each cited claim against current facts.",
                "content_type": ContentType.pdf,
                "status": SubmissionStatus.in_review,
                "text": "Aurelia Foods seasonal campaign draft. Our cheap Heritage Sourdough is guaranteed to cure fatigue. It is 100% safe for everyone and the world's best loaf.",
                "source_filename": "campaign-copy.pdf",
                "source_mime_type": "application/pdf",
                "source_path": "samples/campaign-copy.pdf",
                "source_layout": {"pages": [{"page": 1, "width": 612, "height": 792}], "regions": []},
                "review_finding": {
                    "id": "demo-finding-pdf-claim",
                    "clause": "CLAIM-1",
                    "match": "guaranteed to cure fatigue",
                    "issue": "This superlative is not supported by an approved source.",
                    "category": FindingCategory.unsupported_claim,
                    "location": {"page": 1, "bbox": [70, 590, 400, 615], "media": "pdf"},
                },
            },
            {
                "id": "demo-submission-review-pricing",
                "title": "DEMO · Pantry Subscription Price Card",
                "intent": "Present the current monthly subscription price clearly.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.in_review,
                "text": "The Artisan Pantry Subscription box costs $28 per month.",
                "review_finding": {
                    "id": "demo-finding-review-pricing",
                    "fact_statement": "The Artisan Pantry Subscription box is priced at $34 per month including shipping.",
                    "match": "$28",
                    "issue": "Your text vs approved value — your text: '$28'; approved value: '$34 per month'. Source: Pricing Schedule Q1 2024.",
                    "category": FindingCategory.factual_accuracy,
                    "suggested_rewrite": "$34",
                    "location": None,
                },
            },
            {
                "id": "demo-submission-review-superlative",
                "title": "DEMO · Pantry Box Campaign Claim",
                "intent": "Promote the pantry subscription to new patrons.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.in_review,
                "text": "Our pantry box is guaranteed to be the best in the world.",
                "review_finding": {
                    "id": "demo-finding-review-superlative",
                    "clause": "CLAIM-1",
                    "match": "guaranteed",
                    "issue": "This absolute promotional claim needs reviewer verification.",
                    "category": FindingCategory.unsupported_claim,
                    "location": None,
                },
            },
            {
                "id": "demo-submission-review-free-offer",
                "title": "DEMO · Free Trial Promotion",
                "intent": "Announce a limited free subscription offer.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.in_review,
                "text": "Try the Artisan Pantry Subscription box free for 30 days.",
                "review_finding": {
                    "id": "demo-finding-review-free-offer",
                    "clause": "CLAIM-1",
                    "match": "free for 30 days",
                    "issue": "Review the offer terms, eligibility, and required legal wording.",
                    "category": FindingCategory.unsupported_claim,
                    "location": None,
                },
            },
            {
                "id": "demo-submission-typo-resubmission",
                "title": "DEMO · Pantry Product Page Copy",
                "intent": "Describe the pantry box in clear, accurate language.",
                "content_type": ContentType.text,
                "status": SubmissionStatus.changes_requested,
                "text": "Our artisan pantry box is only $28 and is the best choise for every famly.",
            },
        ]

        for s_data in samples:
            existing = db.query(Submission).filter(Submission.title == s_data["title"]).first()
            if existing is not None:
                existing.is_demo = True
                if existing.status == SubmissionStatus.in_review and reviewer_u and not existing.assigned_to_id:
                    existing.assigned_to_id = reviewer_u.id
                sub = existing
                ver = db.query(SubmissionVersion).filter_by(submission_id=sub.id, version_no=1).first()
            else:
                sub = Submission(
                    id=s_data.get("id"),
                    creator_id=creator_u.id,
                    assigned_to_id=(reviewer_u.id if reviewer_u and s_data["status"] == SubmissionStatus.in_review else None),
                    title=s_data["title"],
                    intent=s_data["intent"],
                    content_type=s_data["content_type"],
                    status=s_data["status"],
                    is_demo=True,
                )
                db.add(sub)
                db.flush()

                source_file = None
                if s_data.get("source_path"):
                    source_file = (Path(__file__).resolve().parents[2] / s_data["source_path"]).read_bytes()
                ver = SubmissionVersion(
                    submission_id=sub.id,
                    version_no=1,
                    text=s_data["text"],
                    source_file=source_file,
                    source_mime_type=s_data.get("source_mime_type"),
                    source_filename=s_data.get("source_filename"),
                    source_layout=s_data.get("source_layout"),
                    created_by=creator_u.id,
                )
                db.add(ver)
                db.flush()

            if ver is None:
                continue

            review_finding = s_data.get("review_finding")
            if review_finding:
                fact_statement = review_finding.get("fact_statement")
                if fact_statement:
                    source = db.query(ApprovedFact).filter_by(statement=fact_statement).one_or_none()
                    if source is None:
                        raise ValueError(f"Demo finding {review_finding['id']} references a missing approved fact")
                    source_type = SourceType.approved_fact
                else:
                    source = clause_objs.get(review_finding["clause"])
                    source_type = SourceType.guideline_clause
                if source:
                    finding = db.get(Finding, review_finding["id"])
                    if finding is None:
                        span_start = max(0, ver.text.find(review_finding["match"]))
                        finding = Finding(
                            id=review_finding["id"],
                            submission_id=sub.id,
                            version_id=ver.id,
                            span_start=span_start,
                            span_end=span_start + len(review_finding["match"]),
                            category=review_finding["category"],
                            issue=review_finding["issue"],
                            source_type=source_type,
                            source_id=source.id,
                            source_quote=source.statement if fact_statement else source.text,
                            suggested_rewrite=review_finding.get("suggested_rewrite"),
                            severity=FindingSeverity.major,
                            confidence=FindingConfidence.high,
                            needs_human=True,
                            status=FindingStatus.open,
                            location=review_finding["location"],
                        )
                        db.add(finding)
                    elif fact_statement and finding.status == FindingStatus.open:
                        finding.issue = review_finding["issue"]
                        finding.source_type = source_type
                        finding.source_id = source.id
                        finding.source_quote = source.statement
                        finding.suggested_rewrite = review_finding.get("suggested_rewrite")

            if existing is not None:
                continue

            # Add comments and approvals for realism
            if s_data["status"] == SubmissionStatus.approved:
                appr = Approval(
                    submission_id=sub.id,
                    version_id=ver.id,
                    user_id=manager_u.id if manager_u else creator_u.id,
                    decision=ApprovalDecision.approved,
                    note="Checked against sourcing facts and tone guidelines. Approved for publication.",
                )
                db.add(appr)
            elif s_data["status"] == SubmissionStatus.changes_requested:
                appr = Approval(
                    submission_id=sub.id,
                    version_id=ver.id,
                    user_id=reviewer_u.id if reviewer_u else creator_u.id,
                    decision=ApprovalDecision.changes_requested,
                    note="Please adjust superlative descriptions and verify holiday pricing before resubmitting.",
                )
                db.add(appr)
                comm = Comment(
                    submission_id=sub.id,
                    user_id=reviewer_u.id if reviewer_u else creator_u.id,
                    body="Reviewer flagged: Check regional distribution claims before final approval.",
                )
                db.add(comm)
            elif s_data["status"] == SubmissionStatus.rejected:
                db.add(Approval(
                    submission_id=sub.id,
                    version_id=ver.id,
                    user_id=manager_u.id if manager_u else creator_u.id,
                    decision=ApprovalDecision.rejected,
                    note="The unsupported health and safety claims need evidence before this can proceed.",
                ))

    # Keep one visible, reproducible feedback pattern in the local demo data:
    # three distinct disputed findings on one clause produce a high DFI and a
    # suppressed normalized span. Fixed IDs make this safe to run repeatedly.
    feedback_clause = clause_objs.get("VOICE-1")
    if creator_u and manager_u and feedback_clause:
        demo_submission_id = "demo-feedback-pattern"
        demo_version_id = "demo-feedback-pattern-v1"
        if db.get(Submission, demo_submission_id) is None:
            demo_submission = Submission(
                id=demo_submission_id,
                creator_id=creator_u.id,
                title="DEMO · Disputed wording feedback",
                intent="Fictional history used to demonstrate guideline insights.",
                content_type=ContentType.text,
                status=SubmissionStatus.checked,
            )
            db.add(demo_submission)
            db.flush()
            db.add(SubmissionVersion(
                id=demo_version_id,
                submission_id=demo_submission_id,
                version_no=1,
                text="Our wording is unclear.",
                created_by=creator_u.id,
            ))
            db.flush()
            for index in range(3):
                finding_id = f"demo-feedback-finding-{index + 1}"
                db.add(Finding(
                    id=finding_id,
                    submission_id=demo_submission_id,
                    version_id=demo_version_id,
                    span_start=0,
                    span_end=23,
                    category=FindingCategory.tone,
                    issue="The voice guidance needs clarification.",
                    source_type=SourceType.guideline_clause,
                    source_id=feedback_clause.id,
                    severity=FindingSeverity.minor,
                    confidence=FindingConfidence.high,
                    status=FindingStatus.disputed,
                ))
                db.add(Decision(
                    id=f"demo-feedback-decision-{index + 1}",
                    finding_id=finding_id,
                    user_id=manager_u.id,
                    action=DecisionAction.dispute,
                    original_span="Our wording is unclear.",
                    reason=(
                        "The voice wording is not clear enough."
                        if index == 0
                        else "The voice guidance is unclear to our team."
                    ),
                ))

    db.commit()
    logger.info("BrandGuard database seed completed successfully.")
