from lux.kit import obs_to_game_state, GameState
from lux.config import EnvConfig
from lux.utils import direction_to, my_turn_to_place_factory
import numpy as np
import sys
import torch as th
from nn import load_policy
from wrappers import SimpleUnitDiscreteController
from wrappers import SimpleUnitObservationWrapper
import os.path as osp

# change this to use weights stored elsewhere
# make sure the model weights are submitted with the other code files
# any files in the logs folder are not necessary
MODEL_WEIGHTS_RELATIVE_PATH = "./best_model.zip"


class Agent():
    def __init__(self, player: str, env_cfg: EnvConfig) -> None:
        self.player = player
        self.opp_player = "player_1" if self.player == "player_0" else "player_0"
        np.random.seed(0)
        self.env_cfg: EnvConfig = env_cfg

        directory = osp.dirname(__file__)
        # load our RL policy
        self.policy = load_policy(osp.join(directory, MODEL_WEIGHTS_RELATIVE_PATH))
        self.policy.eval()
        
        self.controller = SimpleUnitDiscreteController(self.env_cfg)

    def bid_policy(self, step: int, obs, remainingOverageTime: int = 60):
        return dict(faction="AlphaStrike", bid=0)
    def factory_placement_policy(self, step: int, obs, remainingOverageTime: int = 60):
        if obs["teams"][self.player]["metal"] == 0:
            return dict()
        potential_spawns = list(zip(*np.where(obs["board"]["valid_spawns_mask"] == 1)))
        potential_spawns_set = set(potential_spawns)
        done_search = False
        # if player == "player_1":
        ice_diff = np.diff(obs["board"]["ice"])
        pot_ice_spots = np.argwhere(ice_diff == 1)
        if len(pot_ice_spots) == 0:
            pot_ice_spots = potential_spawns
        trials = 5
        while trials > 0:
            pos_idx = np.random.randint(0, len(pot_ice_spots))
            pos = pot_ice_spots[pos_idx]

            area = 3
            for x in range(area):
                for y in range(area):
                    check_pos = [pos[0] + x - area // 2, pos[1] + y - area // 2]
                    if tuple(check_pos) in potential_spawns_set:
                        done_search = True
                        pos = check_pos
                        break
                if done_search:
                    break
            if done_search:
                break
            trials -= 1
        spawn_loc = potential_spawns[np.random.randint(0, len(potential_spawns))]
        if not done_search:
            pos = spawn_loc

        metal = obs["teams"][self.player]["metal"]
        return dict(spawn=pos, metal=metal, water=metal)

    def act(self, step: int, obs, remainingOverageTime: int = 60):
        # first convert observations using the same observation wrapper you used for training
        # note that SimpleUnitObservationWrapper takes input as the full observation for both players and returns an obs for players
        raw_obs = dict(player_0=obs, player_1=obs)
        obs = SimpleUnitObservationWrapper.convert_obs(raw_obs, env_cfg=self.env_cfg)
        obs = obs[self.player]
        
        obs = th.from_numpy(obs).float()
        with th.no_grad():
            # NOTE: we set deterministic to False here, which is only recommended for RL agents
            # that create too many invalid actions (less of an issue if you train with invalid action masking)

            # to mitigate some performance drops, we have a rule based action mask generator for the controller used
            # which will force the agent to generate actions that are valid only.
            action_mask = th.from_numpy(self.controller.action_masks(self.player, raw_obs)).unsqueeze(0).bool()
            actions = self.policy.act(obs.unsqueeze(0), deterministic=False, action_masks=action_mask).cpu().numpy()
        lux_action = self.controller.action_to_lux_action(self.player, raw_obs, actions[0])
        return lux_action
