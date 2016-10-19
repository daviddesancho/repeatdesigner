"""

This file is part of the RepeatDesigner package


"""
import multiprocessing as mp
import designlib
import Bio.PDB
import Bio.Seq
import Bio.SeqUtils

class Design(object):
    """
    A class with everything necessary to define a protein design.

    Attributes
    ----------
    pdb         the PDB file name we use as template

    name        the name of the protein

    targets     the regions to model

    compete     the competing regions when we need to introduce negative design

    """

    def __init__(self, pdb=None, targets=None):
        """
        Parameters
        ----------
        pdb : string
            Name of PDB file to use as template.

        targets : list
            Residues to mutate in order to improve global energy.


        """
        self.pdb = pdb
        self.name = self._pdb_name()
        self.seq, self.struc = self._read_pdb()
        self.targets = self._parse_targets(targets)
        print " Generated new protein design "
        print " .. name : %s"%self.name
        print " .. file : %s"%self.pdb
        print " .. sequence : %s"%self.seq
        print " .. target residues : ",targets

    def _pdb_name(self):
        ie = self.pdb.rfind('.pdb')
        return self.pdb[:ie]

    def _read_pdb(self):
        """ Reads PDB file.

        Returns 
        -------
        seq : str
            Sequence in one letter format.

        struc : obj
            Protein structure.

        """
        parser = Bio.PDB.PDBParser()
        struc = parser.get_structure(self.name, self.pdb)
        seq = Bio.Seq.Seq(''.join([Bio.SeqUtils.seq1(x.get_resname()) for x in \
                struc.get_residues()]))
        return seq, struc

    def _parse_targets(self, targets):
        """ 
        Parse target regions for modelling

        Parameters
        ----------
        targets : list
            List of residues to model.

        Returns
        -------
        list
            List of residues to model

        """
        if targets is None:
            return range(len(self.seq))
        else:
            if all([x in range(len(self.seq)) for x in targets]):
                return targets
            else: 
                raise ValueError(" Input values incompatible with protein sequence.")

class Repeat(Design):
    """
    A class with everything necessary to define a protein repeat design

    Attributes
    ----------
    repeats     The regions corresponding to protein repeats

    """
    def __init__(self, pdb=None, targets=None, repeats=None):
        """
        Parameters
        ----------
        compete : list
            Lists of residues for negative design.
        """
        Design.__init__(self, pdb=pdb, targets=targets)
        self.repeats = _parse_repeats(repeats)

    def _parse_repeats(repeats):
        """ Checks whether repeats are same length and sequence.
        
        Parameters
        ----------
        repeats : list
            List of lists containing repeat indexes

        """
        return repeats

class Optimizer(object):
    """ A class for defining and running an MC sequence optimization

    Attributes
    ----------
    len_mc      The length of the optimization.

    beta        The inverse temperature for simulated annealing


    """

    def __init__(self, design, nruns=1, len_mc=10, beta=1.):
        """
        Parameters
        ----------
        design : object
            The instance of the Design or Repeat class to optimize.

        len_mc : int
            Length of optimization

        beta : float
            Inverse temperature.

        """
        self.design = design
        self.nruns = nruns
        self.len_mc = len_mc
        self.beta = beta
        self.models = {}

    def run_mc(self):
        """ Parallel MC run generator
    
        """
        #  Multiprocessing options
        nproc = mp.cpu_count()
        if self.nruns < nproc:
            pool = mp.Pool(self.nruns)
        else:
            pool = mp.Pool(nproc-1)

        # Do it!
        results = []
        input_des = [[x, [self.design.name, self.beta, self.len_mc, self.design.targets]] for x in range(self.nruns)]
        results = pool.map(designlib.model_mc_worker, input_des)
        pool.close()
        pool.join()
        #for x in range(self.nruns):
        #    results.append(designlib.model_mc_worker(input_des[x]))

        # Parse results
        for x in range(self.nruns):
            mdl, ener_mc = results[x]
            self.models[x] = {}
            self.models[x]['model'] = mdl
            self.models[x]['score'] = ener_mc       
