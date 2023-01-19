# Hydra Submitit Launcher Chunked
Provides a [`Submitit`](https://github.com/facebookincubator/submitit) based Hydra Launcher supporting [SLURM](https://slurm.schedmd.com/documentation.html).
This launcher, in contrast to the [`standard`](https://github.com/facebookresearch/hydra/blob/main/plugins/hydra_submitit_launcher/README.md) submitit Hydra Launcher uses SLURM's functionality to spawn multiple tasks per node to execute more than one job per resource. This however prohibits lanching jobs that would spawn multiple jobs themselves using the SLURM configuration `tasks_per_node` to execute the same application with the same parameter set mutliple times in parallel. This implies, that applications launched by this Launcher should always set `tasks_per_node` to `1` and never utilize the local or global rank information of the spawned SLURM jobs.

# Installation

1. Clone the repository: ```git clone```
2. Navigate into the project directory: `cd hydra_submitit_chunked_launcher`
3. Install using pip: ```pip install .```

# Usage

This plugin registers two Hydra Launchers, namely `submitit_chunked_local` and `submitit_chunked_slurm` for local and distributed execution respectively. Supply the parameter `hydra.launcher.max_num_jobs_per_node` to set how many jobs (i.e. tasks) are spawned on the same node. See `example/` for an exemplary usage. See [website](https://hydra.cc/docs/plugins/submitit_launcher) for more information on the `submitit` Hydra Lancher plugin this code is based on.