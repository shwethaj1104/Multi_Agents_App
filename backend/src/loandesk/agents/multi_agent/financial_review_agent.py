# Assess deterministic financial results and explicitly identify uncertain source inputs.
def run_financial_review_agent(runtime, application, context):
    return runtime.assess("financial_analyst", application, context)
