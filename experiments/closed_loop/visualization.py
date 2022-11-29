
import multiprocessing 
import socket
import pdb
import math
import sys
import os
import datetime
import time
import numpy as np
import random
import collections

# Oscilloscope Imports
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
matplotlib.use("TkAgg")
matplotlib.rcParams['toolbar'] = 'None' 


NB_PTS = 100
LINE = "________________________________________"

class Oscilloscope:
    
    def __init__(self, args, labels, output_q, end_of_sim):
        self.fig = []
        self.axs = []
        self.t = []
        self.gui = args.gui
        self.line_plt_ud = LINE
        self.line_plt_lr = LINE
        self.labels = labels
        self.n = len(labels)
        self.spike_q = multiprocessing.Queue()
        self.output_q = output_q
        self.end_of_sim = end_of_sim
        if self.gui == 1:
            self.p_visual = multiprocessing.Process(target=self.animation, args=())
        else:
            self.p_visual = multiprocessing.Process(target=self.cmdline, args=())
        self.p_o_data = multiprocessing.Process(target=self.get_outputs, args=())
    
    def __enter__(self):
        self.p_visual.start()
        self.p_o_data.start()

    def __exit__(self, e, b, t):
        self.p_visual.join()
        self.p_o_data.join()

    def get_outputs(self):
        
        dt = 0.100
        
        start = time.time()
        current_t = time.time()
        next_check = current_t + dt

        spike_times = []
        spike_count = np.zeros((self.n,))
        nb_spikes_max = 100
        for i in range(self.n):  # 4 motor neurons          
            spike_times.append(collections.deque(maxlen=nb_spikes_max))
            
        while True:

            # Check if the spinnaker simulation has ended
            if self.end_of_sim.value == 1:
                time.sleep(1)
                print("No more outputs to be received")
                break

            while not self.output_q.empty():
                out = self.output_q.get(False)
                current_t = time.time()
                elapsed_t = (current_t - start)*1000
                spike_times[out].append(elapsed_t)
            
            if current_t >= next_check:
                # print(f"Checking @ t={current_t}")
                next_check = current_t + dt
                for i in range(self.n):  
                    train = np.array(spike_times[i])
                    short_train = train[train>(current_t-dt-start)*1000]
                    # print(f"For MN[{i}]: {len(train)} >= {len(short_train)} (Train vs Short Train)")
                    spike_count[i] = len(short_train)
                self.spike_q.put(spike_count, False)

            time.sleep(0.005)

    def get_counts(self,spike_count):

        while not self.spike_q.empty():
            spike_count = self.spike_q.get(False)
            
            if int(spike_count[0])>10 and int(spike_count[1])<10:
                self.line_plt_lr = self.line_plt_lr[1:]+"^"
            if int(spike_count[0])<10 and int(spike_count[1])>10:
                self.line_plt_lr = self.line_plt_lr[1:]+"_"

            if int(spike_count[2])>10 and int(spike_count[3])<10:
                self.line_plt_ud = self.line_plt_ud[1:]+"^"
            if int(spike_count[2])<10 and int(spike_count[3])>10:
                self.line_plt_ud = self.line_plt_ud[1:]+"_"

            print(self.line_plt_ud+"\t\t\t"+self.line_plt_lr+"\r", end = '')
        
        return spike_count

    def rt_plot(self, i, mn, spike_count):
        
        spike_count = self.get_counts(spike_count)                

        # Add x and y to lists
        self.t.append(time.time())
        self.t = self.t[-NB_PTS:]


        max_y = 200

        for j in range(self.n):
            mn[j].append(spike_count[j])
            mn[j] = mn[j][-NB_PTS:]

            self.axs[j].clear()
            self.axs[j].scatter(self.t, mn[j], color='g')
            self.axs[j].xaxis.set_visible(False)
            self.axs[j].set_ylabel(self.labels[j])
            self.axs[j].set_ylim([0,max_y])



        if self.end_of_sim.value == 1:
                time.sleep(1)
                print("No more data to be visualized.")
                plt.savefig('EndOfSim.png')
                plt.close(self.fig)
    
    def cmdline(self):

        spike_count = -NB_PTS*np.ones((self.n,))
        while(True):            
            spike_count = self.get_counts(spike_count) 
            time.sleep(0.001)

    def animation(self):

        print("Starting Oscilloscope")

        # Create figure for plotting
        self.fig, self.axs = plt.subplots(self.n, figsize=(8, 8))
        self.fig.canvas.manager.set_window_title('World Space')

        mn = []
        for i in range(4):
            mn.append([])

        i = 0
        spike_count = -NB_PTS*np.ones((self.n,))

        # Set up plot to call rt_xyz() function periodically
        ani = animation.FuncAnimation(self.fig, self.rt_plot, fargs=(mn, spike_count), interval=1)
        plt.show()