
import os
import sys
s = "/".join(os.getcwd().split("/")[:-1]) + '/utils'
sys.path.append(s)                  # Include utils module

import pyglet
import threading
import tensorflow as tf
import time

from Agent import Agent
from QNetwork import QNetwork
from ExperienceBuffer import ExperienceBuffer

import GUI
import Saver
import Displayer

from settings import Settings


################################################################################
#                                    DEBUG                                     #
from tensorflow.python.client import timeline

class Sess(tf.Session):
    def __init__(self, options, meta, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.op = options
        self.meta = meta
    def run(self, *args, **kwargs):
        return super().run(options=self.op, run_metadata=self.meta, *args, **kwargs)
#                                                                              #
################################################################################


if __name__ == '__main__':

    tf.reset_default_graph()

################################################################################
#                                    DEBUG                                     #
    # options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
    # meta = tf.RunMetadata()
    # config = tf.ConfigProto(log_device_placement=True,
    #                       device_count={"CPU:12", "GPU:1"},
    #                       inter_op_parallelism_threads=10)

    # with Sess(options, meta, config=config) as sess:
#                                                                              #
################################################################################

    with tf.Session() as sess:

        saver = Saver.Saver(sess)
        #displayer = Displayer.Displayer()
        buffer = ExperienceBuffer()


        threads = []
        for i in range(Settings.NB_ACTORS):
            agent = Agent(sess, i, buffer)
            threads.append(threading.Thread(target=agent.run))

        # with tf.device('/device:GPU:0'):
        learner = QNetwork(sess, saver, buffer)
        threads.append(threading.Thread(target=learner.run))

        if not saver.load():
            sess.run(tf.global_variables_initializer())

        for t in threads:
            t.start()

        print("Running...")

        try:
            while not gui.STOP:
                time.sleep(1)

        except KeyboardInterrupt:
            pass

        for t in threads:
            t.join()

################################################################################
#                                    DEBUG                                     #
        # f_t = timeline.Timeline(meta.step_stats)
        # chrome_trace = f_t.generate_chrome_trace_format()
        # with open("timeline.json", 'w') as f:
        #     f.write(chrome_trace)
#                                                                              #
################################################################################

        saver.save(learner.total_eps)

