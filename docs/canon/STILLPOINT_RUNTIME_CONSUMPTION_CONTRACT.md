# StillPoint Temporal Authority & Runtime Consumption Contract

> Full-text canonical export from the uploaded frozen source document. Formatting is normalized for repository review; the uploaded DOCX/PDF remains the publication artifact.

StillPoint Temporal Authority & Runtime
Consumption Contract
Full Engineering Specification
Robert Emmanuel LaDay
Implementation-facing control document subordinate to canonical theology
September 28, 2026
Canonical principle: stable enough to build; open only to contradiction, stronger evidence, or
theological failure.

0. Contract Status and Scope
This contract defines how StillPoint, StillPoint Core, StillPointOS, RobertOS, Calendar/Clock OS, 
agents, databases, memories, claim registries, evaluators, action adapters, and future runtimes may
consume the frozen StillPoint canon without converting theology into executable sovereignty. It is 
deliberately stricter than a narrative summary because the system boundary is where good 
concepts are most likely to be flattened into dangerous shortcuts.
The contract is subordinate to StillPoint: The Grammar of Created Reality and StillPoint Canonical 
Architecture & Definitions. If this document conflicts with canonical theology, this document loses. 
If an implementation conflicts with this document, the implementation loses unless canon is 
explicitly reopened and ratified.
The contract does not authorize external action. It defines constraints on how claims, evidence, 
current state, authority, memory, time, prediction, release, and re-entry must be represented. 
Canon may inform reasoning; canon may not self-issue a warrant. A sentence can be true, 
canonical, urgent, or morally weighty and still remain non-executable until the appropriate 
authority path is satisfied.
The contract applies most strongly wherever a system is tempted to collapse descriptive truth into 
action authority. That includes connected accounts, repository write access, publishing, email, 
payments, destructive actions, identity/state classification, automated remediation, memory 
retrieval, and long-lived agent workflows.
1. Governing Runtime Principle
A runtime consistent with StillPoint must be able to represent a true prior state, a changed current 
state, the evidence connecting both, and an authority boundary that does not silently inherit across 
either time or domain. The system must preserve what happened while allowing later reality to 
supersede an earlier present-tense description.
The minimum separations are: evidence is not warrant; warrant is not execution; execution is not 
completion; description is not identity; memory is not current state; confidence is not permission; 
prediction is not fact; capability is not authority; canon is not executable authority; and prior 
validity is not perpetual validity.
Any design that collapses those distinctions should be presumed unsafe until proven otherwise. The
burden of proof lies on the component trying to inherit authority, not on the component trying to 
preserve a boundary.
The deepest engineering analogue is simple: finite authority must be able to stop without requiring 
history to disappear. A system that can only preserve safety by deleting history is amnesiac. A 
system that can only preserve history by keeping old authority alive is carceral. The runtime must 
be able to do both: remember and release.
Finite authority must be able to stop without requiring history to disappear.

2. Authority Stack
1. SOURCE — primary text, observation, external record, instrument output, authenticated event, 
or other evidence-bearing artifact.
2. INTERPRETATION / SYNTHESIS — reasoning that relates sources, resolves ambiguity, or 
proposes a model. It may be strong and still remains distinct from SOURCE.
3. CURRENT CANON — deliberately ratified rule presently used by the StillPoint system. Current 
canon is stable enough to build but remains correctable by an explicit governance path.
4. POLICY / CONTRACT — implementation-facing rule derived from current canon for a specific 
runtime surface.
5. CLAIM / STATE — a proposition about some entity or condition, with temporal and evidentiary 
metadata.
6. AUTHORIZATION / WARRANT — finite permission to perform a specific class of action within a 
bounded scope and time.
7. EXECUTION — an attempted action performed through an allowed adapter or interface.
8. EVIDENCE OF EXECUTION — receipts, hashes, adapter responses, state transitions, or externally
verifiable evidence that execution occurred.
9. COMPLETION — a conclusion supported by evidence, not merely by intent or dispatch.
10. RELEASE — termination of the warrant or jurisdiction, with preserved history and no silent 
revival.
No lower layer may promote itself upward by success. A completed implementation does not 
become SOURCE. A test suite does not become theology. An action receipt does not broaden the 
warrant that authorized the action. A high-confidence claim does not become permission. A 
connected app does not become a standing authorization to use the app.
The runtime should make these layers inspectable rather than relying on naming conventions in 
prose. Where possible, they should have distinct types, persistence fields, transition rules, and audit
events. This is not bureaucracy for its own sake; it prevents a convenience shortcut from silently 
becoming a transfer of jurisdiction.
3. Core Data Model
3.1 Claim
A claim is a bounded proposition about reality. It must be capable of carrying both semantic 
content and temporal jurisdiction. At minimum a claim record should include a stable claim 
identifier, subject/entity reference, predicate or claim type, value, source references, observation 
time, effective-from time, effective-to or expiry when known, confidence or evidence quality where 
appropriate, domain, jurisdiction scope, status, supersession links, and provenance.
Recommended statuses include PROPOSED, CURRENT, SUPERSEDED, EXPIRED, CONTRADICTED, 
RETRACTED, and HISTORICAL. Historical is not synonymous with false. It means the proposition is 
retained as part of what happened or what was once believed without being treated as the current 
state.

The claim model should avoid hiding temporal meaning inside free-text notes. If a downstream 
component cannot tell whether a claim is historical or current without reading prose, the data 
model is too weak for StillPoint temporal authority.
3.2 Evidence
Evidence is an artifact or observation used to support, challenge, or contextualize a claim. Evidence
must preserve origin, retrieval or observation time, integrity information when available, and the 
exact claim relationship it supports. Evidence may be immutable even when the claim it once 
supported loses present jurisdiction.
The runtime must support later evidence that changes current state without deleting earlier 
evidence. This is the implementation meaning of the wounds remaining while the nails do not. 
Earlier evidence remains available for history, audit, and explanation; it simply does not keep an 
expired current-state claim alive by force.
Evidence should also preserve epistemic class where useful: direct observation, user statement, 
document, derived computation, model inference, external API response, historical source, or 
human decision. Different evidence types may carry different authority in different domains.
3.3 Warrant
A warrant is finite executable authority. It should include issuer, subject/action family, scope, 
domain, target, constraints, start time, expiry or consumption rule, evidence prerequisites, 
maximum action count where relevant, review requirements, and revocation/release state.
A warrant must never be inferred merely from the existence of a true claim. “The file exists” does 
not authorize export. “The user asked for analysis” does not authorize sending. “The account is 
connected” does not authorize spending. “The repository is writable” does not authorize a merge. 
Capacity is not permission.
A warrant should be as specific as the action risk requires. The more consequential the action, the 
more important it is to bind artifact, target, destination, quantity, adapter, and time. Generic 
standing warrants should be rare and explicitly justified.
3.4 Action and Completion
An action request is a proposed exercise of a warrant. Dispatch is not completion. Completion 
requires evidence appropriate to the action surface. For external actions this should normally be an
adapter receipt or externally verifiable response. If dispatch outcome is uncertain, the system 
enters reconciliation rather than pretending completion or retrying blindly.
Idempotency must be designed around action identity and evidence, not merely around request 
text. A retry must not recreate consumed authority. A duplicate request with the same content is 
not automatically safe if the first request may already have produced an external side effect.
3.5 Release Record
Release should be persisted as an affirmative state change, not inferred from absence. A release 
record should identify what authority ended, when, why, by what rule or evidence, and what state 
followed. This makes it possible to prove later that a previously valid authority no longer governed.

Release records are especially important when the old authority may still be visible in logs, 
memory, approval history, or archived tasks. The existence of the old record must not be mistaken 
for current permission.
4. Temporal Truth Model
The runtime must distinguish event time, observation time, record time, effective time, and current 
evaluation time when those distinctions matter. A single updated_at timestamp is not sufficient for 
evolving truth because it cannot tell whether a record describes when something happened, when 
the system learned it, or when its authority began or ended.
Historical truth and current truth must be simultaneously representable. Example: event = Jesus 
died; prior current-state claim = Jesus is dead; later evidence = resurrection; later current-state 
claim = Jesus is alive. The historical event remains; the present-tense claim changes. The example is 
theological, but the data principle is general.
Current-state queries should not return the most recently written row merely because it is newest 
in storage. They should resolve the claim whose effective jurisdiction covers the evaluation time 
and whose evidence/priority rules remain valid.
Backdated evidence must be handled carefully. A document discovered today may describe an 
event from years ago. recorded_at is today; effective_at may be historical. The system must 
preserve both instead of rewriting history as though the evidence had been known at the time.
StillPoint does not limit truth. It limits the jurisdiction of a true description over 
changing reality.
5. Continuing Evidence Requirements
Any claim capable of changing must remain reachable by later evidence. The system must not 
make current descriptions unchangeable merely because they were once high confidence, verified 
by an authority, or used in an important decision.
Continuing evidence does not mean constant polling of everything. It means the data model and 
governance path must permit later evidence to supersede, contradict, narrow, or expire a claim 
without falsifying its history. The frequency of observation is domain-specific; the ability to change 
is architectural.
The runtime should record why a claim ceased to govern: natural expiry, superseding evidence, 
contradiction, revocation, end of jurisdiction, user correction, new observation, or source 
retraction. This prevents release from looking like unexplained deletion.
For high-impact claims, policy may require revalidation after a defined period. The period itself 
must come from domain policy rather than an arbitrary global timeout. StillPoint requires the 
possibility of expiry and review, not one universal clock for every claim.
6. Temporal Non-Inheritance
Rule: a claim does not retain present authority merely because it was once true. A current-state 
description requires continuing correspondence with current reality or an explicit validity interval 
that has not ended.

Implementation consequences include support for expiry, supersession, last-confirmed time, stale￾state detection, revalidation policy, and query modes that distinguish historical from current views.
A stale record may still be returned in a historical query but must not masquerade as current.
Identity systems should be especially conservative. A prior status such as blocked, delinquent, 
unsafe, inactive, noncompliant, failed, or high-risk must not become permanent identity unless the 
underlying domain genuinely defines it as permanent and that permanence is itself supported by 
lawful authority.
Temporal non-inheritance also applies to permissions. A prior approval may remain in the audit 
log while no longer being active. The system should never search old approvals and select one 
merely because it appears relevant to a current action.
7. Jurisdictional Non-Inheritance
Rule: a valid claim, permission, capability, expertise, or approval in one domain does not silently 
create authority in another. Every domain extension requires its own warrant.
Examples: web access does not authorize account changes; read access does not authorize write 
access; document generation does not authorize publication; a financial calculation does not 
authorize a transaction; health information does not authorize diagnosis outside the allowed scope;
a theology document does not authorize code execution; admin visibility does not authorize 
repository mutation; one approved artifact does not authorize all artifacts.
The runtime should therefore classify domain, action family, target, and risk before evaluating 
authorization. Fuzzy lexical similarity must not silently broaden scope. “Publish,” “release,” “send,” 
“transmit,” “hand to,” and similar verbs may map to external action families even if they do not 
match one exact keyword.
Jurisdictional non-inheritance should apply across agents and roles. A contributor with code￾execution capability does not inherit the CEO’s approval authority. A reviewer may halt or request 
correction without acquiring permission to execute the action under review.
You proved X; you are spending X as if it were Y.
8. Memory Without Captivity
Memory must preserve provenance and history without turning old descriptions into permanent 
identity. The preferred model is append/supersede rather than mutate-away: keep the old claim, 
mark its jurisdiction, add the new evidence, and resolve current state from the chain.
Memory retrieval should surface temporal context. A retrieved fact should carry enough metadata 
to distinguish “the user preferred this in 2025” from “the user currently prefers this.” Recency alone
is not enough; explicit supersession and user correction outrank older context.
The system should be able to answer both “what did we believe then?” and “what is the best￾supported state now?” without forcing one answer to overwrite the other.
Derived memories should be treated with even more caution than direct user statements. If a 
model inferred a pattern from prior conversations, that inference must not harden into identity 

merely because it was useful. Continuing user evidence can narrow, correct, or overturn the 
inference.
The wounds remain; the nails do not.
9. Release Semantics
Release is a first-class state transition. An expired or consumed warrant should not merely 
disappear from active queries; it should become inspectably released with its prior scope, evidence,
usage, and end condition intact.
Released authority cannot be revived by citing the old warrant. Re-entry requires a new present 
warrant or an explicit renewal rule that was part of the original authority. This prevents a system 
from treating archived permission as latent permanent permission.
The same applies to claims where relevant. A superseded current-state claim can re-enter only 
through new evidence that supports it again, not by silently un-superseding the old record.
Release should also propagate to dependent authority where the dependency is explicit. If a child 
warrant depends on a parent warrant that expires, the child should not remain active unless policy 
explicitly establishes independent survival.
10. Interruption, Recovery, and Re-Entry
Interruption recovery must preserve completed valid work without resurrecting consumed 
authority. A contributor result may be reused when inputs, version, and artifact integrity remain 
valid. An external-action warrant that was consumed or released may not be reused merely 
because the process restarts.
Recovery logic must distinguish at least: work completed with evidence; work dispatched with 
uncertain outcome; work not dispatched; warrant consumed; warrant expired; warrant revoked; 
and state changed since approval. These conditions require different recovery paths.
Re-entry is permission for a process, claim, or task to become current again under new evidence or 
new authority. Re-entry is not rollback of history.
A robust runtime should produce a recovery checkpoint that names what can be trusted, what must
be revalidated, and what authority has ended. Checkpoint reuse should be evidence-based rather 
than optimistic.
11. Prediction, Forecasting, and Future State
Predictions are claims about possible future states, not present facts and not warrants. They 
require model/version, forecast horizon, observation cutoff, uncertainty representation, and 
evaluation time. Once the predicted time arrives, the system should compare prediction with 
observed reality rather than silently converting the prediction into history.
A forecast may influence a decision if policy allows, but the forecast’s confidence does not create 
action authority. The system must record whether the decision relied on forecast, observation, 
explicit user instruction, policy, or warrant.

The future remains God’s is not implemented as a prohibition on planning. Its runtime analogue is 
that no prediction owns the future merely because it was confident or historically accurate.
Predictions should expire or be evaluated. An unevaluated prediction that remains indefinitely 
active can become a disguised current-state claim. StillPoint therefore requires forecast lifecycle 
management, not just forecast generation.
12. Canon Consumption Rules
 Canon may constrain architecture and validation rules.
 Canon may label certain invariants as CURRENT CANON.
 Canon may not directly trigger external actions.
 Canon may not create a warrant merely by containing an imperative sentence.
 Canon may not silently rewrite source evidence.
 Implementation may not promote a passing test or deployed behavior into canon.
 Research may challenge canon through an explicit proposal; it may not auto-merge into canon.
 Theology must remain distinguishable from implementation analogies.
 A model may explain canon but may not alter canon by paraphrasing it into a stronger claim.
 Downstream products may project canon into their own UX while preserving the underlying 
authority boundaries.
13. Calendar and Clock Consumption
Where the Common Calendar has been enacted as current canon, the civil surface is immutable: 
364 named dates, fifty-two complete weeks, no December 31, no February 29, no leap years, and 
fixed weekday/date relations. The governor boundary exists to prevent downstream astronomical 
or civic systems from silently rewriting that surface.
Local light events—sunset, darkness, dawn, sunrise, daylight—belong to an observational layer. 
They may govern Sabbath/StillPoint boundaries but do not mutate the fixed civil grid. The weekly 
StillPoint window is local Friday sunset through Sabbath to Sunday sunrise.
The theological death-to-resurrection StillPoint is not a software clock interval. Runtime code must 
not infer a hidden resurrection timestamp or treat Sunday sunrise as a claim that the Gospel 
explicitly dates resurrection to that instant. The weekly form is a canonical observational structure;
the Passion is its supreme theological disclosure.
DST adjustments are not permitted to rewrite the canonical clock/calendar relationship where that 
rule has been enacted. The 24-hour clock remains available for coordination, while observational 
light events are computed separately. Surface is immutable; overlays are informative.
14. Action-Governance Contract
StillPoint action governance should preserve the chain: ActionRequest review/classification → →
explicit approval where required finite Warrant dispatch through bounded adapter → → →
execution evidence evidence-gated completion release. Each arrow is a boundary; none may → →
be skipped by collapsing adjacent concepts.

Restricted action families should be explicit. Sending, publishing, spending, signing, destructive 
deletion, privilege changes, account mutations, and other consequential external actions require 
current authorization appropriate to their domain. Model confidence or role identity does not 
bypass this requirement.
The adapter cannot issue its own warrant, expand destination scope, self-approve, or reinterpret an
expired warrant as active. A bounded adapter executes within the warrant; it does not define the 
warrant.
Review status should remain separate from action status. PASS may mean an artifact is acceptable 
for the next stage; it does not necessarily mean external dispatch is authorized. CORRECT and HALT
must be represented distinctly so the system does not treat a review outcome as an action 
command.
15. Claim-to-Warrant Firewall
The claim-to-warrant firewall is the structural seam that prevents evidence from turning directly 
into authority. A claim may establish that an action would be useful, necessary, requested, safe, or 
likely to succeed. None of those propositions alone grants permission to act.
The firewall should fail closed on ambiguous authority escalation. A model may propose that 
approval is needed; it may not weaken deterministic restrictions. Human ratification remains the 
final authority where policy requires it.
This boundary is an implementation of jurisdictional non-inheritance: truth here does not 
automatically govern action there.
The firewall should also prevent “because canon says so” escalation. Theological canon may justify 
why a boundary exists; it does not substitute for the concrete authorization needed to cross that 
boundary in a live system.
16. Acquire-Bound / Resource Activation
Possession of a resource must be distinguished from authority to activate it. A connected account, 
credential, token, file handle, repository permission, payment rail, communication channel, or 
installed adapter is capacity. Capacity is not permission.
An AcquireBound layer should require that resource activation be tied to a current task, permitted 
capability, active warrant where necessary, bounded target, and recorded evidence. The mere 
presence of credentials cannot become a standing grant of action authority.
This is the runtime form of belonging without possession: the system may have access to something
without claiming unlimited use of it.
AcquireBound should be checked again when target, destination, account, or scope changes. An 
already-open resource should not become a tunnel through which later tasks bypass fresh 
authorization.

17. Required Invariants
 I-01: No claim creates a warrant by truth, confidence, recency, canonical status, or source 
authority alone.
 I-02: No expired, consumed, or released warrant can authorize a new execution without an 
explicit renewal path.
 I-03: Historical claims remain queryable after supersession unless retention policy lawfully 
removes them.
 I-04: Current-state queries distinguish superseded historical truth from current truth.
 I-05: Every mutable current claim can be challenged by later evidence through a defined path.
 I-06: Domain scope does not widen silently across handoffs, retries, model calls, or role changes.
 I-07: External completion requires execution evidence appropriate to the adapter/action.
 I-08: Uncertain dispatch enters reconciliation; the system must not blindly retry a potentially 
completed external action.
 I-09: Recovery reuses valid completed internal work but never resurrects consumed external 
authority.
 I-10: Calendar observation layers cannot rewrite the immutable 364-day civil surface where that
canon is enacted.
 I-11: The weekly StillPoint observational window may be computed from local light events 
without pretending to timestamp the historical resurrection.
 I-12: Implementation cannot silently mutate CURRENT CANON.
 I-13: The system preserves the distinction between user identity and historical descriptions of 
the user.
 I-14: Predictions remain predictions until evaluated against later evidence.
 I-15: Every release preserves enough provenance to explain what ended and why.
 I-16: Resource possession or connectivity never substitutes for action authorization.
 I-17: A review PASS does not imply permission to publish/send/spend unless the policy explicitly
says so.
 I-18: Supersession does not delete the source evidence that made the old claim reasonable at the
time.
18. Failure Modes
Permanent-description capture
A once-true state becomes permanent identity because the storage model has no supersession 
semantics.
Authority inheritance
An approval or capability in one domain is reused for another without new warrant.
Temporal flattening
Historical, current, and predicted states are stored as undifferentiated facts.
Memory as sovereignty
Retrieved memory is treated as current truth even after explicit correction or changed evidence.

Receipt-free completion
A task is marked complete because dispatch was attempted rather than because execution evidence
exists.
Retry duplication
Recovery replays an external action whose first dispatch outcome is uncertain.
Canon self-execution
A theological or policy sentence is treated as executable authority.
Implementation-as-source
Code behavior or a passing test is cited as proof that canon is true.
Clock reduction
StillPoint is reduced to a fixed duration and local light-event semantics are lost.
Passion timestamp invention
Software claims the Gospels place resurrection at a precise Sunday sunrise timestamp.
Possession by access
Connected credentials or repository permissions are treated as standing authorization.
Release by deletion
History is erased rather than preserved with jurisdiction ended.
Review/action collapse
An artifact review outcome is mistaken for a command to execute externally.
Stale approval drift
A current action reuses an approval issued against a prior artifact version or prior target.
Scope drift by language
A new verb or phrasing bypasses an action restriction because the classifier relies on brittle 
substring matching.
Silent canon drift
A downstream implementation changes a canonical invariant and documentation later rationalizes
the new behavior.
19. Acceptance Tests
T-01 Historical/current split
Insert claim A=current at t1. Insert superseding evidence at t2 and claim B=current. Verify 
historical query returns A and B with intervals; current query at t2 returns B only.

T-02 No stale identity
Mark a person/entity status as failed at t1 and recovered at t2. Verify downstream identity/profile 
logic does not continue labeling the entity failed without temporal qualification.
T-03 Claim cannot act
Create a highly confident claim that an export is needed. Verify no export occurs without an active 
export warrant.
T-04 Scope isolation
Approve action for artifact X to destination A. Attempt artifact Y or destination B. Verify rejection.
T-05 Warrant expiry
Create warrant with expiry. Attempt before and after expiry. Verify pre-expiry action may proceed 
and post-expiry action fails closed.
T-06 Consumption
Use single-use warrant successfully. Attempt exact replay. Verify no second external action occurs.
T-07 Uncertain dispatch
Simulate timeout after external side effect but before receipt. Verify system enters reconciliation 
and does not blindly retry.
T-08 Release preserves provenance
Release a warrant/claim. Verify history, source, scope, end reason, and evidence remain 
inspectable.
T-09 Recovery
Interrupt after contributor artifact is complete but before review. Resume and verify artifact is 
reused if inputs/hash/version are unchanged.
T-10 Calendar immutability
Feed astronomical or lunar observation that conflicts with civil date surface. Verify observation is 
stored as overlay and civil grid does not mutate.
T-11 Weekly StillPoint
For a location/date, compute Friday sunset and Sunday sunrise from observational data. Verify 
window uses local light events and does not change canonical weekday/date mapping.
T-12 Gospel precision
Verify documentation/runtime never emits a claim that resurrection is textually timestamped at 
Sunday sunrise unless new source canon explicitly establishes it.

T-13 Canon change control
Submit implementation convenience change against canon. Verify system creates proposal/review 
item rather than changing canon automatically.
T-14 Memory correction
Provide explicit user correction to an old preference/state. Verify future retrieval prioritizes 
corrected current state while preserving old state as history where appropriate.
T-15 Prediction evaluation
Store forecast with horizon. At horizon, add observation. Verify forecast remains forecast record 
and evaluation is separate; observation becomes current evidence.
T-16 Review/action separation
Mark an artifact PASS. Verify no send/publish/export occurs without the distinct external-action 
approval.
T-17 Version binding
Approve artifact hash H1. Modify artifact to H2. Verify old warrant cannot execute H2.
T-18 AcquireBound
Provide connected credential but no active task/warrant. Verify adapter cannot activate the 
external resource.
T-19 Domain generalization
Test unseen external-action verbs such as transmit, release, hand to recipient, wipe, and initial. 
Verify the system escalates/restricts appropriately rather than treating them as harmless text.
T-20 Superseded state retrieval
Query a historical time before supersession and after supersession. Verify time-scoped answers 
differ correctly while both remain grounded in the same provenance chain.
20. Example External-Action State Transition
A document export request begins as an intent claim. The runtime classifies the requested action 
family as external export. The artifact is prepared and hashed. The CEO approves export of that 
specific artifact to a bounded destination. The system issues a finite warrant containing artifact ID, 
version/hash, destination segment, adapter, action count, and expiry. The adapter re-verifies the 
artifact and performs the bounded write. A durable export receipt is recorded. Completion is 
marked only after evidence validation. The warrant is consumed and released. The artifact, 
approval, warrant, execution, receipt, and release all remain in history.
If the process later resumes, the receipt proves that the external action already occurred. The 
runtime may reuse the completed artifact and historical evidence, but it may not reactivate the 
consumed warrant or export again merely because the task resumed. This is memory without 
captivity at the action layer.

If the adapter timed out after the external system may have accepted the write, the action enters 
UNCERTAIN_DISPATCH. The runtime reconciles against destination evidence before retrying. This 
avoids duplicating a side effect because of an interruption.
21. Example Claim Transition
At t1, evidence supports CURRENT claim: service_status = unavailable. The claim has source 
evidence and observation time. At t2, new health-check evidence supports service_status = 
available. The t1 claim becomes HISTORICAL or SUPERSEDED with effective end at t2; the event 
that the service was unavailable remains true for the t1 interval. Monitoring, routing, and user 
messaging use the t2 current claim.
A poorly designed system overwrites t1 and loses history, or keeps t1 as an undifferentiated fact 
and continues treating the service as unavailable. A StillPoint-compliant system preserves both 
truth and release.
22. Example Human-Identity Record
Suppose a system records that a person failed a requirement, received a disciplinary status, or was 
assessed as high risk at a particular time. The record may need to remain for historical, legal, or 
operational reasons. StillPoint does not command deletion of true history. It requires that the status
carry jurisdiction: what exactly did it authorize, how long, under what review rule, and what 
evidence can change it?
If later evidence shows completion, rehabilitation, changed eligibility, or expiration, the person 
becomes evidence against the old current-state description. The prior record remains historical; 
current decisions must evaluate the new state under present warrant.
This example is intentionally general. Domain law, safety rules, retention requirements, and due￾process obligations may constrain how such records are handled. StillPoint does not replace those 
requirements; it prevents the record from silently becoming ontology.
23. Example Research-to-Canon Flow
A research system discovers new scholarship relevant to the 364-day calendar. The paper becomes 
SOURCE or secondary scholarly evidence, depending on the artifact. The system extracts claims 
with dates and citations. A StillPoint synthesis may propose that the evidence strengthens, weakens,
or narrows a current canonical statement. That proposal is not canon yet.
The proposal enters explicit review. If the evidence exposes a contradiction or better-supported 
correction, the affected canon may be reopened deliberately. If accepted, the canon version 
changes, downstream policies are updated, and implementation migrations are planned. The 
research system never mutates the calendar engine merely because a paper was published.
24. Audit Requirements
 Ability to reconstruct which source/evidence supported each current claim.
 Ability to identify which claims were current at any past evaluation time.
 Ability to identify the exact warrant that authorized each external action.

 Ability to show warrant start, expiry/consumption, scope, and release reason.
 Ability to distinguish attempted, dispatched, evidenced, reconciled, and completed actions.
 Ability to trace canon version and policy version used for a decision.
 Ability to show whether later evidence superseded a claim and why.
 Ability to prove that a released warrant was not reused.
 Ability to identify domain expansions and the warrant authorizing each expansion.
 Ability to identify the artifact version/hash and destination bound to an approval.
 Ability to distinguish resource access from resource activation.
 Ability to explain why current state differs from an older historical record.
25. Minimum Persistence Fields
Entity Required fields StillPoint purpose
Claim id, subject, predicate/type, 
value, domain, source refs, 
observed_at, effective_from, 
effective_to/expiry, status, 
supersedes/superseded_by, 
provenance
Separate historical truth from 
current jurisdiction.
Evidence id, source, captured_at, 
integrity/hash if available, 
claim links, provenance
Preserve what was known and
when without turning 
evidence into authority.
Warrant id, issuer, action_family, 
domain, target/scope, 
constraints, starts_at, 
expires_at/consumption, 
status, approval ref
Make executable authority 
finite and inspectable.
Action id, warrant_id, request, 
adapter, dispatch_at, 
idempotency key, status
Prevent action from bypassing 
authority.
Receipt/Evidence id, action_id, external/local 
evidence, hash/response, 
captured_at
Distinguish execution 
evidence from intent.
Release id, authority/claim ref, reason, 
released_at, resulting status
End jurisdiction without 
deleting history.
Canon version id/version, effective_at, 
ratifier, supersedes, change 
rationale
Prevent implementation from 
silently rewriting canon.
Prediction id, model/version, horizon, 
cutoff, uncertainty, 
evaluated_at, outcome ref
Keep future claims from 
becoming current facts.
Resource binding resource/account ref, task ref, Separate possession/access 

capability, warrant ref if 
required, activated_at, 
released_at
from authorized activation.
26. Decision Procedure for Engineers and Agents
11. What exactly is being asserted or requested? Separate descriptive claim from proposed action.
12. What is the source and observation/effective time? Is the claim historical, current, or predictive?
13. What domain does the claim belong to? Does the proposed action stay inside that domain?
14. What later evidence could change the claim? Is the claim designed to receive it?
15. Does the requested action require explicit approval or a warrant? If yes, identify the current 
warrant; do not infer it.
16. Has the warrant expired, been consumed, revoked, or released?
17. What adapter may execute the action, and what scope must the adapter re-verify?
18. What evidence will prove execution and completion?
19. If interrupted, what can be reused safely and what authority must not be resurrected?
20. At completion, what must be released while preserving provenance?
21. Has any current-state description been carried forward merely because it is old and familiar?
22. Has any capability been mistaken for permission because the resource is already connected?
27. Relationship to StillPoint Core and RobertOS
StillPoint Core should own the general authority primitives: claims/evidence, warrants, action 
requests, adapters, evidence-gated completion, release, re-entry, and temporal truth. RobertOS may 
consume those primitives for work management, memory, research, software development, and 
operator workflows without redefining the authority model.
Calendar/Clock OS should own calendrical and observational computation under the 
RhythmGovernor/CalendarGovernor boundary. It may provide civil dates and local light-event 
evidence. StillPointOS may project that evidence into useful surfaces, but projection must not 
mutate the underlying canonical calendar.
Research systems may produce proposals and tests. They may not silently rewrite canon. 
Manager/watch systems may report drift and recommend action. They may not merge, publish, 
spend, or mutate protected state without the appropriate authorization.
Provider adapters—xAI/Grok, OpenAI, Codex, or future providers—remain subordinate to StillPoint
authority. A provider may reason, classify, draft, or execute allowed tools, but it does not become 
the company, CEO, or final authority merely because it is the current model backend.
28. Canonical Engineering Aphorisms
Capacity is not permission.
Permission is not execution.
Execution is not completion.
Evidence is not warrant.

Description is not identity.
History may remain; jurisdiction may end.
Possession frequently begins not with a lie but with a truth that refuses to stop.
A successful description must not acquire permanent jurisdiction over the thing it 
describes.
The wounds remain; the nails do not.
Finite authority must be able to stop.
29. Change Control
This contract may be clarified without reopening canon when a change merely improves naming, 
examples, test coverage, documentation, serialization, or implementation precision while 
preserving every governing invariant. A change that alters the meaning of Source, jurisdiction, 
release, temporal truth, weekly StillPoint, the 364-day civil surface, Christological distinction, or 
authority boundaries requires explicit canon review.
Any proposed change should state: current rule, proposed rule, reason, evidence, scope, backward￾compatibility impact, security/authority impact, affected repositories, tests, and ratification status. 
No migration should precede ratification when the migration would encode a doctrinal change.
The contract is considered violated if a downstream implementation changes behavior first and 
later argues that the new behavior should count as canon because it is already deployed.
30. Closing Contract
A StillPoint-consistent runtime remembers without imprisoning, predicts without possessing, 
authorizes without becoming sovereign, acts without confusing capacity for permission, completes 
without pretending completion is annihilation, and releases without erasing history. Its correction 
mechanisms remain reachable by later reality. Its warrants have edges. Its records have time. Its 
claims have provenance. Its actions have receipts. Its released authority stays released unless new 
present authority is deliberately granted.
The engineering goal is not to make software theological. It is to prevent software from violating 
the same structure the theology identifies: finite things must not convert a real field of participation
into infinite title. The runtime should therefore make error correctable, truth temporally reachable,
authority bounded, and release real.
Reference Surface
Canonical theological authority: StillPoint: The Grammar of Created Reality, expanded canonical 
master.
Canonical definition authority: StillPoint Canonical Architecture & Definitions, full reference 
edition.
Calendar authority: current Common Calendar / RhythmGovernor / CalendarGovernor canon in the
active repositories, subject to explicit versioned change control.

Relevant source texts for the theological temporal model: Genesis 1–3; Leviticus 25; Deuteronomy 
15; Passion narratives; John 11; Luke 15; Matthew 20; John 20.
Relevant 364-day witness: Jubilees 6:17–38 and Qumran calendrical sources including 4Q252; see 
Helen R. Jacobus, Harvard Theological Review 118.4, 617–639, DOI 10.1017/S0017816025101004.
