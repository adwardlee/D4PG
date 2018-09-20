
import tensorflow as tf
import numpy as np
from collections import deque

from Model import build_actor
from network_utils import copy_vars, get_vars
from Environment import Environment

from settings import Settings


class Agent:
    """
    This class builds an agent that interacts with an environment to gather
    experiences and put them into a buffer.
    """

    def __init__(self, sess, n_agent, gui, displayer, buffer):
        print("Initializing agent %i..." % n_agent)

        self.n_agent = n_agent
        self.sess = sess
        self.gui = gui
        self.displayer = displayer
        self.buffer = buffer

        self.env = Environment()

        self.build_actor()
        self.build_update()

        self.create_summaries()

        print("Agent initialized !\n")

    def create_summaries(self):

        self.ep_reward_ph = tf.placeholder(tf.float32)
        ep_reward_summary = tf.summary.scalar("Episode/Episode reward", self.ep_reward_ph)

        self.steps_ph = tf.placeholder(tf.float32)
        steps_summary = tf.summary.scalar("Episode/Nb steps", self.steps_ph)

        self.noise_ph = tf.placeholder(tf.float32)
        noise_summary = tf.summary.scalar("Settings/Noise", self.noise_ph)

        self.ep_summary = tf.summary.merge([ep_reward_summary,
                                            noise_summary,
                                            steps_summary])

        self.writer = tf.summary.FileWriter(f"./logs/Agent_{self.n_agent}",
                                            self.sess.graph)

    def build_actor(self):
        """
        Build a copy of the learner's actor network to allow the agent to
        interact with the environment on its own.
        """
        scope = 'worker_agent_' + str(self.n_agent)
        self.state_ph = tf.placeholder(dtype=tf.float32,
                                       shape=[None, *Settings.STATE_SIZE],
                                       name='state_ph')

        # Get the policy prediction network
        self.policy = build_actor(self.state_ph, trainable=False, scope=scope)
        self.vars = get_vars(scope, trainable=False)

    def build_update(self):
        """
        Build the operation to copy the weights of the learner's actor network
        in the agent's network.
        """
        with self.sess.as_default(), self.sess.graph.as_default():

            self.network_vars = get_vars('learner_actor', trainable=True)
            self.update = copy_vars(self.network_vars, self.vars,
                                    1, 'update_agent_'+str(self.n_agent))

    def predict_action(self, s):
        """
        Wrapper method to get the action outputted by the actor network.
        """
        return self.sess.run(self.policy, feed_dict={self.state_ph: s[None]})[0]

    def run(self):
        """
        Method to run the agent in the environment to collect experiences.
        """
        print("Beginning of the run agent {}...".format(self.n_agent))

        self.sess.run(self.update)

        self.total_steps = 0
        self.nb_ep = 1

        while self.nb_ep < Settings.TRAINING_EPS and not self.gui.STOP:

            s = self.env.reset()
            episode_reward = 0
            done = False

            memory = deque()
            episode_step = 1
            # The more episodes the agent performs, the longer they are
            max_step = Settings.MAX_EPISODE_STEPS
            if Settings.EP_ELONGATION > 0:
                max_step += self.nb_ep // Settings.EP_ELONGATION

            noise_scale = Settings.NOISE_SCALE * Settings.NOISE_DECAY**(self.nb_ep//20)


            while episode_step < max_step and not done:


                a = np.clip(self.predict_action(s),
                            Settings.LOW_BOUND, Settings.HIGH_BOUND)

                # Add gaussian noise
                noise = np.random.normal(size=Settings.ACTION_SIZE)

                a += noise_scale * noise
                s_, r, done, _ = self.env.act(a)
                episode_reward += r

                memory.append((s, a, r))

                # Keep the experience in memory until 'N_STEP_RETURN' steps has
                # passed to get the delayed return r_1 + ... + gamma^n r_n
                if len(memory) >= Settings.N_STEP_RETURN:
                    s_mem, a_mem, discount_r = memory.popleft()
                    for i, (si, ai, ri) in enumerate(memory):
                        discount_r += ri * Settings.DISCOUNT ** (i + 1)
                    self.buffer.add((s_mem, a_mem, discount_r, s_, 1 if not done else 0))

                s = s_
                episode_step += 1
                self.total_steps += 1

            # Periodically update agents on the network
            if self.nb_ep % Settings.UPDATE_ACTORS_FREQ == 0:
                self.sess.run(self.update)

            if not self.gui.STOP:
                if self.n_agent == 1 and self.gui.ep_reward.get(self.nb_ep):
                    print("Episode %i : reward %i, steps %i, noise scale %f" % (self.nb_ep, episode_reward, episode_step, noise_scale))

                plot = (self.n_agent == 1 and self.gui.plot.get(self.nb_ep))
                self.displayer.add_reward(episode_reward, self.n_agent, plot=plot)

                # Write the summary
                feed_dict = {self.ep_reward_ph: episode_reward,
                             self.noise_ph: noise_scale,
                             self.steps_ph: episode_step}
                summary = self.sess.run(self.ep_summary, feed_dict=feed_dict)
                self.writer.add_summary(summary, self.nb_ep)

                self.nb_ep += 1

        self.env.close()
