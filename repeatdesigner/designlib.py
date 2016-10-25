"""

This file is part of the RepeatDesigner package

"""
import os
import sys
import tempfile
import random
import numpy as np

import Bio.pairwise2
import Bio.SeqUtils
import Bio.SeqIO
import Bio.SeqRecord

import modellerlib as mdlib

def model_mc_worker(mc_input):
    """
    Simple modelling worker function

    Parameters
    ----------
    mc_input : list
        In which we get the input for the MC optimization.
            design : cls
                Instance of the design class. 
            
            beta : float
                Inverse temperature.
        
            len_mc : int
                length of MC run.
        
    """
    # parse input
    run, design, beta, len_mc = parse_mc_input(mc_input)
    pdb = design.name
    targets = design.targets
    if type(design).__name__ == 'Repeat':
        print " I am a repeat protein!"

    # redirect output by keeping track of sys.stdout
#    nb_stdout = sys.stdout # redirect outputnb_stdout = sys.stdout 
#    sys.stdout = open('data/junk%g.out'%run, 'w') 

    # generate modeller environment
    env = mdlib.modeller_main()

    respos = targets #[x.index for x in mdl.residues]
    restyp = ["ALA", "ARG", "ASN", "ASP", "CYS", "GLU", "GLN", "GLY", \
            "HIS", "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", \
            "THR", "TRP", "TYR", "VAL"]

    # generate initial model from PDB file
    mdl = mdlib.get_model(env, file=pdb)
    s = mdlib.get_selection(mdl) 
    seq_prev = design.seq
    ener0 = mdlib.get_energy(s) # calculate initial energy
    contribs = [ener0] #, ener_mut, ener_ab, ener_ba]
    ener_prev = ener0

    n = 0
    ener_mc = [contribs]
    while True:
        rp = random.choice(respos) # randomly select position
        rt = random.choice(restyp) # randomly select residue

        # build model for actual mutation
        print seq_prev,
        print rp,
        print rt
        seq, ener = gen_mutated_models(env, design=design, \
                seq_prev=seq_prev, rp=rp, rt=rt)
                
        # standard acceptance rejection criterion
        seq_prev, ener_prev = boltzmann(ener, \
                ener_prev, seq, seq_prev, beta)

        contribs = [ener_prev]
#        current = 'data/old%g.pdb'%run
        print " Current energy %g\n"%ener_prev
        ener_mc.append(contribs)

        n +=1

        if n >= len_mc:
            # wrap up
            # write mutant sequence to file
            Bio.SeqIO.write(Bio.SeqRecord.SeqRecord(seq_prev, id="data/final%g.fasta"%run), \
                    open("data/final%g.fasta"%run, "w"), "fasta")
            # align sequence and template
            align = mdlib.gen_align(env, pdb=design.pdb, mut="data/final%g.fasta"%run, out="data/align%g.fasta"%run)
            # generate model
            mdl = mdlib.get_automodel(env, "data/align%g.fasta"%run, "data/final%g.fasta"%run, design.pdb)


            ali_tf = tempfile.NamedTemporaryFile(prefix='ali_', suffix='.fasta', \
                delete=False)

            #mdl = mdlib.get_model(env, file=current)
            mdlib.write_model(mdl, file="data/final_run%s"%run + ".pdb")
            #os.remove('data/mutant%g.pdb'%run)
            break
#    sys.stdout = nb_stdout # redirect output    
    return ener_mc

def parse_mc_input(mc_input):
    """
    Parses multiprocessing input

    """
    run = mc_input[0]
    design = mc_input[1][0]
    beta = mc_input[1][1]
    len_mc = mc_input[1][2]
    return run, design, beta, len_mc

def gen_models(env, seq_mut=None, pdb=None):
    """ Generate models based on sequence 

    Parameters
    ----------
    seq_mut : object
        Instance of Seq class.

    pdb : str
        PDB filename for template.

    Returns
    -------
    mdl : object
        Instance of Modeller's model class.

    """
    # write mutant sequence to temporary file
    mut_tf = tempfile.NamedTemporaryFile(prefix='mut_', suffix='.fasta', \
            delete=False)
    Bio.SeqIO.write(Bio.SeqRecord.SeqRecord(seq_mut, id=mut_tf.name), \
            mut_tf.name, "fasta")
    mut_tf.close()

    # align sequence and template
    ali_tf = tempfile.NamedTemporaryFile(prefix='ali_', suffix='.fasta', \
            delete=False)
    align = mdlib.gen_align(env, pdb=pdb, mut=mut_tf.name, out=ali_tf.name)

    # generate model
    mdl = mdlib.get_automodel(env, ali_tf.name, mut_tf.name, pdb)
    
    return mdl

def gen_mutated_models(env, design=None, seq_prev=None, rp=None, rt=None):
    """ Generate mutated model based on sequence

    Includes modelling the mutant for a given sequence and possible 
    competing selections

    Parameters
    ----------
    env :

    design:

    seq_prev : 

    rp : 

    rt : 

    Returns
    -------
    seq_mut : object
        MutableSeq 

    """
    # generate mutation
    seq_mut = mutator(seq_prev, rp, rt)
    print seq_mut

    # generate model for mutant
    mdl = gen_models(env, seq_mut=seq_mut, pdb=design.pdb)

    # calculate energy for whole mutant
    s = mdlib.get_selection(mdl)
    ener = mdlib.get_energy(s)

    # generate competing models
    if type(design).__name__ == 'Repeat':
        #print " I am a repeat protein!"
        # check if mutated residue is in repeat
        try:
            assert any([rp in range(rep[0],rep[1]+1) for rep in design.repeats])
            
            # find position in repeat
            print "Finding mutating residue in repeat"
            for rep in design.repeats:
                if rp in range(rep[0],rep[1]+1):
                    index = range(rep[0], rep[1]+1).index(rp)
                    break
            s = mdlib.get_selection(mdl, sel=mdl.residues[str(index)])
            ener_comp = mdlib.get_energy(s)
            print index

            # build competing model for each repeat             
            print " Building competing models"
            for rep in design.repeats:
                print rep 
                if rp not in range(rep[0],rep[1]+1):
                    seq_comp = mutator(seq_prev, rep[0]+index, rt)
                    print seq_comp
                    mdl = gen_models(env, seq_mut=seq_comp, pdb=design.pdb)
                    s = mdlib.get_selection(mdl, sel=mdl.residues[str(rep[0]+index)])
                    print s
                    ener_comp -= mdlib.get_energy(s)
        except AssertionError:
            print " AssertionError : residue not in repeat"
        
    #    [s.add(mdl.residues["%s:A"%x]) for x in respos]
    #    ener_ba = s.assess_dope()

    #    # build model for competing mutation    
    #    mutations = []
    #    for r in repeatA:
    #        if mdl.residues["%s:A"%r].pdb_name != tpr_residues[r]:
    #            mutations.append((r, mdl.residues["%s:A"%r].pdb_name))
    #    mdl.read(file=pdb)
    #    for r, res in mutations:
    #        mdl = mutate_model(mdl, "%s"%(r-34), rt)
    #    # calculate energy interface AB
    #    s = selection()
    #    [s.add(mdl.residues["%s:A"%x]) for x in respos0]
    #    ener_ab = s.assess_dope()
    #    dener = ener_ba - ener_ab
    #    ener = w*ener_mut + (1.-w)*dener
        return seq_mut, ener
    else:
        return seq_mut, ener

def mutator(seq, rp, rt):
    """
    Generates mutation in Seq space

    Parameters
    ----------
    seq : object
        BioPython Seq object to mutate.

    rp : int
        Index indicating position to mutate.

    rt : str
        1 letter code with amino acid type to introduce.

    Returns
    -------
    object
        BioPython Seq object with mutated sequence.

    """
    try:
        mutable_seq = seq.tomutable()
    except AttributeError:
        mutable_seq = seq
    mutable_seq[rp] = Bio.SeqUtils.seq1(rt)
    return mutable_seq


def boltzmann(ener, ener_prev, seq, seq_prev, beta):
    """ Boltzmann acceptance - rejection

    Parameters
    ----------
    ener : float
        New energy.

    ener_prev : float
        Old energy.

    seq : object
        BioPython Seq object with new sequence.

    seq_prev : object
        BioPython Seq object with old sequence.

    beta : float
        Inverse temperature.

    """
    if ener < ener_prev:
        seq_prev = seq
        ener_prev = ener
    else:
        dener = ener - ener_prev
        if np.exp(-beta*dener) > np.random.random():
            seq_prev = seq
            ener_prev = ener 

    return seq_prev, ener_prev

