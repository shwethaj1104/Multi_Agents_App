# Run the complete investigation through one capable LangChain generalist with shared tools.
def run_loan_review_agent(runtime, application, context):
    return runtime.assess("generalist", application, context)
