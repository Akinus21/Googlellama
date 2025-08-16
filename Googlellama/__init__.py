try:
    from akinus_utils.utils.bootstrap import bootstrap_dependencies
    bootstrap_dependencies()
except Exception as e:
    print(f"[BOOTSTRAP ERROR] {e}")
