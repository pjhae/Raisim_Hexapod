from ruamel.yaml import YAML, dump, RoundTripDumper
from raisimGymTorch.env.bin import hexapod_command_locomotion
from raisimGymTorch.env.RaisimGymVecEnv import RaisimGymVecEnv as VecEnv
from raisimGymTorch.helper.raisim_gym_helper import Command
import raisimGymTorch.algo.ppo.module as ppo_module
import os
import math
import time
import torch
import argparse


# configuration
parser = argparse.ArgumentParser()
parser.add_argument('-w', '--weight', help='trained weight path', type=str, default='')
args = parser.parse_args()

# directories
task_path = os.path.dirname(os.path.realpath(__file__))
home_path = task_path + "/../../../../.."

# config
cfg = YAML().load(open(task_path + "/cfg.yaml", 'r'))

# create environment from the configuration file
cfg['environment']['num_envs'] = 1

# for custom command
command = Command(cfg)
n_steps_command = cfg['environment']['command']['dt'] / cfg['environment']['control_dt']
command_dict = {0:'Go Forward', 1:'Turn Left', 2:'Turn Right'} # should be updated manually when changed!!

env = VecEnv(hexapod_command_locomotion.RaisimGymEnv(home_path + "/rsc", dump(cfg['environment'], Dumper=RoundTripDumper)), cfg['environment'])

# shortcuts
ob_dim = env.num_obs
act_dim = env.num_acts

weight_path = args.weight
iteration_number = weight_path.rsplit('/', 1)[1].split('_', 1)[1].rsplit('.', 1)[0]
weight_dir = weight_path.rsplit('/', 1)[0] + '/'

if weight_path == "":
    print("Can't find trained weight, please provide a trained weight with --weight switch\n")
else:
    print("Loaded weight from {}\n".format(weight_path))
    start = time.time()
    env.reset()
    reward_ll_sum = 0
    done_sum = 0
    average_dones = 0.
    n_steps = math.floor(cfg['environment']['max_time'] / cfg['environment']['control_dt'])
    total_steps = n_steps * 1
    start_step_id = 0

    print("Visualizing and evaluating the policy: ", weight_path)
    loaded_graph = ppo_module.MLP(cfg['architecture']['policy_net'], ob_dim, act_dim)
    loaded_graph.load_state_dict(torch.load(weight_path)['actor_architecture_state_dict'])

    env.load_scaling(weight_dir, int(iteration_number))
    env.turn_on_visualization()

    max_steps = math.floor(cfg['environment']['max_time'] / cfg['environment']['control_dt'])
    iterations = 10

    for it in range(iterations):
        for step in range(max_steps):
            # give command
            if step % n_steps_command == 0:
                sample_command = command.sample_evaluate()
                env.setCommand(sample_command)
                print(command_dict[sample_command[0]])
        
            time.sleep(cfg['environment']['control_dt'])
            obs = env.observe(False)
            action_ll = loaded_graph(torch.from_numpy(obs).cpu())
            reward_ll, dones = env.step(action_ll.cpu().detach().numpy())
            reward_ll_sum = reward_ll_sum + reward_ll[0]
            
            if dones or step == max_steps - 1:
                print('----------------------------------------------------')
                print('{:<40} {:>6}'.format("average ll reward: ", '{:0.10f}'.format(reward_ll_sum / max_steps)))
                print('{:<40} {:>6}'.format("time elapsed [sec]: ", '{:6.4f}'.format(max_steps * cfg['environment']['control_dt'])))
                print('----------------------------------------------------\n')
                start_step_id = step + 1
                reward_ll_sum = 0.0
                
                env.reset()

    env.turn_off_visualization()
    env.reset()
    print("Finished at the maximum visualization steps")
