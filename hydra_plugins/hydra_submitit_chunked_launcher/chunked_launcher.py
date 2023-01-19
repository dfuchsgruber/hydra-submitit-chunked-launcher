# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from hydra.core.singleton import Singleton
from hydra.core.utils import JobReturn, filter_overrides, run_job, setup_globals
from hydra.plugins.launcher import Launcher
from hydra.types import HydraContext, TaskFunction
from omegaconf import DictConfig, OmegaConf, open_dict

from .config import BaseQueueConf

log = logging.getLogger(__name__)


class BaseSubmititLauncher(Launcher):

    _EXECUTOR = "abstract"

    def __init__(self, **params: Any) -> None:
        self.params = {}
        for k, v in params.items():
            if OmegaConf.is_config(v):
                v = OmegaConf.to_container(v, resolve=True)
            self.params[k] = v

        self.config: Optional[DictConfig] = None
        self.task_function: Optional[TaskFunction] = None
        self.sweep_configs: Optional[TaskFunction] = None
        self.hydra_context: Optional[HydraContext] = None

    def setup(
        self,
        *,
        hydra_context: HydraContext,
        task_function: TaskFunction,
        config: DictConfig,
    ) -> None:
        self.config = config
        self.hydra_context = hydra_context
        self.task_function = task_function

    def __call__(
        self,
        sweep_overrides_list: Sequence[List[str]],
        job_dir_keys: Sequence[str],
        job_nums: Sequence[int],
        job_ids: Sequence[str],
        singleton_states: Sequence[Dict[type, Singleton]],
    ) -> Optional[JobReturn]:
        # lazy import to ensure plugin discovery remains fast
        import submitit

        assert self.hydra_context is not None
        assert self.config is not None
        assert self.task_function is not None

        job_environment = submitit.JobEnvironment()
        task_idx = job_environment.global_rank
        
        if task_idx >= len(sweep_overrides_list):
            # If the number of jobs is not divisible by the number of tasks per job
            # some tasks will have nothing to do
            return None
        
        sweep_overrides, job_dir_key, job_num, job_id, singleton_state = \
            sweep_overrides_list[task_idx], job_dir_keys[task_idx], job_nums[task_idx], \
            job_ids[task_idx], singleton_states[task_idx]
            
        Singleton.set_state(singleton_state)
        setup_globals()
        sweep_config = self.hydra_context.config_loader.load_sweep_config(
            self.config, sweep_overrides
        )

        with open_dict(sweep_config.hydra.job) as job:
            # Populate new job variables
            job.id = job_environment.job_id  # type: ignore
            sweep_config.hydra.job.num = job_num

        return run_job(
            hydra_context=self.hydra_context,
            task_function=self.task_function,
            config=sweep_config,
            job_dir_key=job_dir_key,
            job_subdir_key="hydra.sweep.subdir",
        )

    def checkpoint(self, *args: Any, **kwargs: Any) -> Any:
        """Resubmit the current callable at its current state with the same initial arguments."""
        # lazy import to ensure plugin discovery remains fast
        import submitit

        return submitit.helpers.DelayedSubmission(self, *args, **kwargs)

    def launch(
        self, job_overrides: Sequence[Sequence[str]], initial_job_idx: int
    ) -> Sequence[JobReturn]:
        # lazy import to ensure plugin discovery remains fast
        import submitit
        
        assert self.config is not None

        num_jobs = len(job_overrides)
        assert num_jobs > 0
        params = self.params
        
        if params['tasks_per_node'] != 1:
            raise RuntimeError(f'Chunked submitit launcher uses different tasks per node.\n' +
                               'Your code should not use that functionality but sets\n' +
                                f'"hydra.launcher.tasks_per_node" to {params["tasks_per_node"]}.\n' +
                                "Use a number of 1 instead and make your code not rely on mutliple tasks.")
        else:
            chunk_size = params['max_num_jobs_per_node']
            params['tasks_per_node'] = chunk_size
        # build executor
        init_params = {"folder": self.params["submitit_folder"]}
        specific_init_keys = {"max_num_timeout"}

        init_params.update(
            **{
                f"{self._EXECUTOR}_{x}": y
                for x, y in params.items()
                if x in specific_init_keys
            }
        )
        init_keys = specific_init_keys | {"submitit_folder", "max_num_jobs_per_node"}
        executor = submitit.AutoExecutor(cluster=self._EXECUTOR, **init_params)

        # specify resources/parameters
        baseparams = set(OmegaConf.structured(BaseQueueConf).keys())
        params = {
            x if x in baseparams else f"{self._EXECUTOR}_{x}": y
            for x, y in params.items()
            if x not in init_keys
        }
        executor.update_parameters(**params)

        log.info(
            f"Submitit chunked '{self._EXECUTOR}' sweep output dir : "
            f"{self.config.hydra.sweep.dir}"
        )
        sweep_dir = Path(str(self.config.hydra.sweep.dir))
        sweep_dir.mkdir(parents=True, exist_ok=True)
        if "mode" in self.config.hydra.sweep:
            mode = int(str(self.config.hydra.sweep.mode), 8)
            os.chmod(sweep_dir, mode=mode)

        job_params: List[Any] = []
        for idx, overrides in enumerate(job_overrides):
            idx = initial_job_idx + idx
            lst = " ".join(filter_overrides(overrides))
            log.info(f"\t#{idx} : {lst}")
            job_params.append(
                (
                    list(overrides),
                    "hydra.sweep.dir",
                    idx,
                    f"job_id_for_{idx}",
                    Singleton.get_state(),
                )
            )
        
        assert chunk_size > 0 and isinstance(chunk_size, int), f'Invalid chunk size {chunk_size}'
        jobs = executor.map_array(self, *([params[i : i + chunk_size] for i in range(0, len(params), chunk_size)] for params in zip(*job_params)))
        return [j.results()[0] for j in jobs if j]
        #return sum((j.results()[0] for j in jobs), start=[])


class LocalChunkedLauncher(BaseSubmititLauncher):
    _EXECUTOR = "local"


class SlurmChunkedLauncher(BaseSubmititLauncher):
    _EXECUTOR = "slurm"