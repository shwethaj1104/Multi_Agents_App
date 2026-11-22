# Plan independent assignments or synthesize their results using the same supervisor model role.
def run_supervisor_agent(runtime, application, context, *, synthesis=False):
    return runtime.assess(
        "supervisor_synthesis" if synthesis else "supervisor_plan", application, context
    )
