# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from joblib import Parallel, delayed

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
        joblib_config: Dict[str, str]
    ) -> Optional[JobReturn]:

        assert self.hydra_context is not None
        assert self.config is not None
        assert self.task_function is not None
        
        # Use joblib with loky backend for multiple processes per job
        
        assert len(sweep_overrides_list) == len(job_dir_keys) == len(job_nums) == len(job_ids) == len(singleton_states)
        
        runs = Parallel(**joblib_config)(
            delayed(self._call_experiment)(*args) for args in
            zip(sweep_overrides_list, job_dir_keys, job_nums, job_ids, singleton_states)
        )
        assert isinstance(runs, List)   
        for run in runs:
            assert isinstance(run, JobReturn)
        return runs

    def _call_experiment(self, sweep_overrides, job_dir_key, job_num, job_id, singleton_state):
        # lazy import to ensure plugin discovery remains fast
        import submitit
        
        job_environment = submitit.JobEnvironment() 
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
        
        chunk_size = params['max_experiments_per_job']
        # build executor
        init_params = {"folder": self.params["submitit_folder"]}
        specific_init_keys = {"max_num_timeout"}

        # Validate the joblib config
        joblib_config = params['joblib']
        if joblib_config['backend'] != 'loky':
            raise ValueError(f'Hydra is only compatible with the loky joblib backend, not {joblib_config["backend"]}')
        if joblib_config['n_jobs'] > 0 and joblib_config['n_jobs'] < chunk_size:
            logging.warn(f'Running {chunk_size} experiments per job but only providing {joblib_config["n_jobs"]} processes via "n_jobs" to joblib backend.')

        init_params.update(
            **{
                f"{self._EXECUTOR}_{x}": y
                for x, y in params.items()
                if x in specific_init_keys
            }
        )
        init_keys = specific_init_keys | {"submitit_folder", "max_experiments_per_job", "joblib"}
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
        jobs = executor.map_array(self, *([params[i : i + chunk_size] for i in range(0, len(params), chunk_size)] for params in zip(*job_params)),
                                  [joblib_config for i in range(0, len(params), chunk_size)])
        # return [j.results()[0] for j in jobs if j]
        return sum((j.results()[0] for j in jobs), start=[])


class LocalChunkedLauncher(BaseSubmititLauncher):
    _EXECUTOR = "local"


class SlurmChunkedLauncher(BaseSubmititLauncher):
    _EXECUTOR = "slurm"