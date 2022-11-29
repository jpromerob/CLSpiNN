
import multiprocessing 
import argparse
import sys, os, time
import pdb



from visualization import *
from stimulation import *
from computation import *


def parse_args():

    
    parser = argparse.ArgumentParser(description='SpiNNaker-SPIF Simulation with Artificial Data')

    parser.add_argument('-r','--runtime', type=int, help="Run Time, in seconds", default=10)
    parser.add_argument('-i', '--ip', type= str, help="SPIF's IP address", default="172.16.223.98")
    parser.add_argument('-p', '--port', type=int, help="SPIF's port", default=3333)
    parser.add_argument('-m', '--mode', type=str, help="Stimulus mode: auto | manual", default='auto')
    parser.add_argument('-w', '--width', type=int, help="Image size (in px)", default=24)
    parser.add_argument('-n', '--npc', type=int, help="# Neurons Per Core", default=4)
    parser.add_argument('-d', '--dimensions', type=int, help="Dimensions (1D, 2D)", default=1)
    parser.add_argument('-g', '--gui', type=int, help="Use of GUI", default=1)
    

    return parser.parse_args()
   

if __name__ == '__main__':

    args = parse_args()
        
    manager = multiprocessing.Manager()
    end_of_sim = manager.Value('i', 0)
    output_q = multiprocessing.Queue() # events


    spin = Computer(args, output_q)
    stim = Stimulator(args, end_of_sim)
    osci = Oscilloscope(args, spin.labels, output_q, end_of_sim)


    with spin:
        with stim:
            with osci:
            
                spin.run_sim()
                end_of_sim.value = 1 # Let other processes know that simulation stopped
                spin.wrap_up()

    
    