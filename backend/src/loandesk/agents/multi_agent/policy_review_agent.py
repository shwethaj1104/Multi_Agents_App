# Retrieve policy requirements in parallel and leave dependent checks for supervisor synthesis.
def run_policy_review_agent(runtime, application, context):
    return runtime.assess("policy_reviewer", application, context)
