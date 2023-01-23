import logging
import os
import time

import hydra
import submitit
from omegaconf import DictConfig

log = logging.getLogger(__name__)

@hydra.main(version_base=None, config_path=".", config_name="config")
def my_app(cfg: DictConfig) -> None:
    
    log.info(str(cfg))
    env = submitit.JobEnvironment()
    log.info(str(env))
    log.info(f"Process ID {os.getpid()} executing task {cfg.task}, with {env}")
    time.sleep(20)
    log.info(f"Process ID {os.getpid()} finished task {cfg.task}, with {env}")


if __name__ == "__main__":
    my_app()