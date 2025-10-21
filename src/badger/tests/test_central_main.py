import logging
import time
from multiprocessing import Process
from badger.log import get_logging_manager, configure_subprocess_logger


def test_subprocess(log_queue):
    """Simulates your optimization subprocess"""
    configure_subprocess_logger(log_queue=log_queue, log_level="DEBUG")

    sub_logger = logging.getLogger("badger.subprocess")

    for i in range(5):
        sub_logger.debug(f"Debug message {i} from subprocess")
        sub_logger.info(f"Info message {i} from subprocess")
        time.sleep(0.5)


def test_centralized_logging(tmp_path):
    log_filepath = tmp_path / "test_multiprocess.log"
    # Start centralized logging
    logging_manager = get_logging_manager()
    logging_manager.start_listener(log_filepath=str(log_filepath), level="DEBUG")

    # Configure main process logger to ALSO use the queue
    # (This makes main and subprocess symmetric)
    log_queue = logging_manager.get_queue()
    configure_subprocess_logger(log_queue=log_queue, log_level="DEBUG")

    logger = logging.getLogger("badger.main")

    logger.info("Main process: Starting test")

    # Start subprocess
    p = Process(target=test_subprocess, args=(log_queue,))
    p.start()

    # Main process continues logging
    for i in range(5):
        logger.info(f"Main process message {i}")
        time.sleep(0.3)

    p.join()

    logger.info("Main process: Test complete")

    # Small delay to ensure all logs are processed
    time.sleep(0.5)

    # Stop logging
    logging_manager.stop_listener()

    print(
        " Check test_multiprocess.log - you should see interleaved messages from both processes!"
    )
    assert log_filepath.exists()
    assert log_filepath.stat().st_size > 0


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        test_centralized_logging(Path(tmpdir))
