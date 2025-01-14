import logging
import inspect

log = logging.getLogger(__file__)


class MessageDispatcher:
    """Dispatches current message to any registered function: https://github.com/slackapi/bolt-python/issues/786"""

    registered_funcs = []

    def add(self, *args, **kwargs):
        """Adds a function to the dispatcher."""

        def decorator(func):
            if not kwargs.get("name"):
                name = func.__name__
            else:
                name = kwargs.pop("name")

            self.registered_funcs.append(
                {"name": name, "func": func, "exclude": kwargs.pop("exclude", [])}
            )

        return decorator

    def dispatch(self, *args, **kwargs):
        """Runs all registered functions."""
        for f in self.registered_funcs:
            # only inject the args the function cares about
            func_args = inspect.getfullargspec(inspect.unwrap(f["func"])).args
            injected_args = (kwargs[a] for a in func_args)

            if exclude := f["exclude"]:
                subtype: str = kwargs.get("body", {}).get("event", {}).get("subtype", "")
                if subtype in exclude.get("subtype", []):
                    log.debug(f"Skipping dispatched function ({f['name']})")
                    continue

            try:
                f["func"](*injected_args)
            except Exception as e:
                log.exception(e)
                log.debug(f"Failed to run dispatched function ({e})")


message_dispatcher = MessageDispatcher()
