from fastapi import APIRouter, BackgroundTasks, Depends

from loandesk.api.dependencies import get_resources
from loandesk.domain.contracts import DomainError, HumanDecision, ReviewRecord, ReviewRequest

router = APIRouter(tags=["reviews"])


# Start a review in this API's fixed architecture; return immediately while the graph runs in
# background.
@router.post("/applications/{case_id}/reviews", status_code=202, response_model=ReviewRecord)
def start_review(
    case_id: str, payload: ReviewRequest, tasks: BackgroundTasks, resources=Depends(get_resources)
):
    review = resources.reviews.start(case_id, payload.execution_mode)
    tasks.add_task(resources.reviews.execute, review["id"])
    return review


# List current-mode reviews for a case or approval queue, retaining all previous report runs.
@router.get("/reviews", response_model=list[ReviewRecord])
def list_reviews(case_id: str | None = None, resources=Depends(get_resources)):
    filters = {"review_mode": resources.settings.review_mode}
    if case_id:
        filters["case_id"] = case_id
    records = resources.repository.list("reviews", filters)
    visible = {case["id"] for case in resources.applications.list()}
    return [review for review in records if review["case_id"] in visible]


# Read persisted progress and the latest immutable report revision.
@router.get("/reviews/{review_id}", response_model=ReviewRecord)
def get_review(review_id: str, resources=Depends(get_resources)):
    return resources.reviews.get(review_id)


# Apply a human decision to the exact reviewed version, then resume its persisted graph.
@router.post("/reviews/{review_id}/decisions", status_code=202, response_model=ReviewRecord)
def submit_decision(
    review_id: str, payload: HumanDecision, tasks: BackgroundTasks, resources=Depends(get_resources)
):
    if resources.reviews.get(review_id)["review_mode"] != resources.settings.review_mode:
        raise DomainError("Submit this decision through the matching architecture workspace.", 409)
    review = resources.reviews.decide(review_id, payload)
    if review["status"] == "resuming":
        tasks.add_task(resources.reviews.execute, review_id)
    return review


# Resume work explicitly after a server interruption; no paid call is automatically retried at
# startup.
@router.post("/reviews/{review_id}/recover", status_code=202, response_model=ReviewRecord)
def recover_review(review_id: str, tasks: BackgroundTasks, resources=Depends(get_resources)):
    review = resources.reviews.recover(review_id)
    tasks.add_task(resources.reviews.execute, review_id)
    return review
