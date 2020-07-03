import logging

stdout_handler = logging.StreamHandler()
stdout_handler.setLevel(logging.WARNING)
log = logging.getLogger(__name__)
log.addHandler(stdout_handler)
