# Hydra Submitit Launcher Chunked
Provides a [`Submitit`](https://github.com/facebookincubator/submitit) based Hydra Launcher supporting [SLURM](https://slurm.schedmd.com/documentation.html).
This launcher, in contrast to the [`default`](https://github.com/facebookresearch/hydra/blob/main/plugins/hydra_submitit_launcher/README.md) submitit Hydra Launcher can run multiple experiments (i.e. configurations of a sweep) in parallel on one job. To that end, `joblib` and the `loky` backend are used to spawn a process for each experiment within a job.

## Installation

1. Clone the repository: ```git clone https://github.com/WodkaRHR/hydra_submitit_chunked_lancher.git```
2. Navigate into the project directory: `cd hydra_submitit_chunked_launcher`
3. Install using pip: ```pip install .```

## Usage

This plugin registers two Hydra Launchers, namely `submitit_chunked_local` and `submitit_chunked_slurm` for local and distributed execution respectively. Supply the parameter `hydra.launcher.max_experiments_per_job` to set how many jobs (i.e. tasks) are spawned on the same node. See `example/` for an exemplary usage. See [website](https://hydra.cc/docs/plugins/submitit_launcher) for more information on the `submitit` Hydra Lancher plugin this code is based on. You can define arguments passed to the `joblib` backend using the configuration key group `hydra.launcher.joblib`. For example, if you want to limit the number of experiments run in parallel in one job, specify `hydra.launcher.joblib.n_jobs` accordingly.

## Issues

### Jobs crash when `DataLoader`'s `num_workers != 0`

As explained in this [issue](https://github.com/facebookresearch/hydra/issues/964), the joblib launcher (which this launcher is based on) will crash if you set `num_workers` to any number not equal to zero in `DataLoader` instances. The reason behind this is (most likely?) that the way the `DataLoader` realizes paralellism by default clashes with `joblib`. A suggested solution to this problem would be to set `multiprocessing_context='fork'` when initializing `DataLoader` instances. Note that this problem might also occur with other third-party libraries that use paralellism
