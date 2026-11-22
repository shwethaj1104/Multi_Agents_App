# Inspect evidence completeness and contradictions independently of the other specialists.
def run_document_review_agent(runtime, application, context):
    return runtime.assess("document_reviewer", application, context)
