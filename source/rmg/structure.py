#!/usr/bin/python
# -*- coding: utf-8 -*-

################################################################################
#
#	RMG - Reaction Mechanism Generator
#
#	Copyright (c) 2002-2009 Prof. William H. Green (whgreen@mit.edu) and the
#	RMG Team (rmg_dev@mit.edu)
#
#	Permission is hereby granted, free of charge, to any person obtaining a
#	copy of this software and associated documentation files (the 'Software'),
#	to deal in the Software without restriction, including without limitation
#	the rights to use, copy, modify, merge, publish, distribute, sublicense,
#	and/or sell copies of the Software, and to permit persons to whom the
#	Software is furnished to do so, subject to the following conditions:
#
#	The above copyright notice and this permission notice shall be included in
#	all copies or substantial portions of the Software.
#
#	THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#	FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
################################################################################

"""
Contains classes describing chemical entities: elements, atoms, bonds, species, etc.
"""

import logging
import pybel
import openbabel

import chem
import graph

################################################################################

class InvalidAdjacencyListException(Exception):
	"""
	An exception used when parsing an adjacency list to indicate that it is
	invalid. The label of the adjacency list is stored in the `label` attribute.
	"""

	def __init__(self, label):
		self.label = label

	def __str__(self):
		return 'Invalid adjacency list: ' + self.label


################################################################################

class Structure:
	"""
	A representation of a chemical species using a graph data structure. The
	vertices represent atoms, while the edges represent bonds.
	"""

	def __init__(self, atoms=None, bonds=None):
		self.initialize(atoms or [], bonds or [])

	def atoms(self):
		"""
		Return a list of the atoms in the structure.
		"""
		return self.graph.keys()

	def bonds(self):
		"""
		Return a list of the bonds in the structure.
		"""
		bondlist = []
		for atom1 in self.graph:
			for atom2 in self.graph[atom1]:
				bond = self.graph[atom1][atom2]
				if bond not in bondlist:
					bondlist.append(bond)
		return bondlist

	def addAtom(self, atom):
		"""
		Add `atom` to the graph as a vertex. The atom is initialized with
		no edges.
		"""
		self.graph[atom] = {}
		return atom

	def addBond(self, bond):
		"""
		Add `bond` to the graph as an edge connecting atoms `atom1` and
		`atom2`, which must already be present in the graph.
		"""
		atom1 = bond.atoms[0]; atom2 = bond.atoms[1]
		self.graph[atom1][atom2] = bond
		self.graph[atom2][atom1] = bond
		return bond

	def getBonds(self, atom):
		"""
		Return a list of the bonds involving the specified `atom`.
		"""
		if atom not in self.graph: return []
		else: return self.graph[atom]

	def getBond(self, atom1, atom2):
		"""
		Returns the bond connecting atoms `atom1` and `atom2` if it exists, or
		:data:`None` if not.
		"""
		if self.hasBond(atom1, atom2):	return self.graph[atom1][atom2]
		else:							return None

	def hasBond(self, atom1, atom2):
		"""
		Returns true if atoms `atom1` and `atom2`, are in the graph and
		are connected by a bond.
		"""
		if atom1 in self.graph.keys():
			if atom2 in self.graph[atom1].keys():
				return True
		return False

	def removeAtom(self, atom):
		"""
		Remove `atom` from the graph as a vertex. Also removes all bonds
		associated with `atom`. Does not remove atoms that no longer have any
		bonds as a result of this removal.
		"""
		if atom not in self.graph: return
		for atom2 in self.graph:
			if atom2 is not atom:
				if atom in self.graph[atom2]:
					del self.graph[atom2][atom]
		del self.graph[atom]

	def removeBond(self, bond):
		"""
		Remove `bond` from the graph. Does not remove atoms that no longer have
		any bonds as a result of this removal.
		"""
		atom1 = bond.atoms[0]; atom2 = bond.atoms[1]
		del self.graph[atom1][atom2]
		del self.graph[atom2][atom1]

	def isIsomorphic(self, other):
		"""
		Returns :data:`True` if two graphs are isomorphic and :data:`False`
		otherwise. Uses the VF2 algorithm of Vento and Foggia.
		"""
		return graph.VF2_isomorphism(self.graph, other.graph, {}, {}, False, False)

	def isSubgraphIsomorphic(self, other, map12=None, map21=None):
		"""
		Returns :data:`True` if `other` is subgraph isomorphic and :data:`False`
		otherwise. Uses the VF2 algorithm of Vento and Foggia.
		"""
		return graph.VF2_isomorphism(self.graph, other.graph, map21, map12, True, False)

	def findSubgraphIsomorphisms(self, other):
		"""
		Returns :data:`True` if `other` is subgraph isomorphic and :data:`False`
		otherwise. Uses the VF2 algorithm of Vento and Foggia.
		"""
		return graph.VF2_isomorphism(self.graph, other.graph, {}, {}, True, True)

	def initialize(self, atoms, bonds):
		"""
		Rebuild the `graph` data member based on the lists of atoms and bonds
		provided in `atoms` and `bonds`, respectively.
		"""
		self.graph = {}

		if atoms is None or bonds is None:
			return

		for atom in atoms:
			self.graph[atom] = {}
		for bond in bonds:
			self.graph[bond.atoms[0]][bond.atoms[1]] = bond
			self.graph[bond.atoms[1]][bond.atoms[0]] = bond

	def getFormula(self):
		"""
		Return the molecular formula for the structure.
		"""
		mol = pybel.Molecule(self.toOBMol())
		return mol.formula

	def fromAdjacencyList(self, adjlist):
		"""
		Convert a string adjacency list `adjlist` into a structure object.
		"""

		try:

			atoms = []; bonds = []; atomdict = {}; bonddict = {}

			lines = adjlist.splitlines()

			label = lines[0]

			for line in lines[1:]:

				data = line.split()

				# Skip if blank line
				if len(data) == 0:
					continue

				# First item is index for atom
				# Sometimes these have a trailing period (as if in a numbered list),
				# so remove it just in case
				aid = int(data[0].strip('.'))

				# If second item is '*', the atom is the center atom
				center = ''
				index = 1
				if data[1][0] == '*':
					center = data[1]
					index = 2

				# Next is the element or functional group element
				# A list can be specified with the {,} syntax
				elements = data[index]
				if elements[0] == '{':
					elements = elements[1:-1].split(',')
				else:
					elements = [elements]

				# Next is the electron state
				elecState = data[index+1].upper()
				if elecState[0] == '{':
					elecState = elecState[1:-1].split(',')
				else:
					elecState = [elecState]

				# Create a new atom based on the above information
				atom = chem.Atom(elements, elecState, 0, center)

				# Add the atom to the list
				atoms.append(atom)
				atomdict[aid] = atom

				bonddict[aid] = {}

				# Process list of bonds
				for datum in data[index+2:]:

					# Sometimes commas are used to delimit bonds in the bond list,
					# so strip them just in case
					datum = datum.strip(',')

					aid2, comma, btype = datum[1:-1].partition(',')
					aid2 = int(aid2)

					if btype[0] == '{':
						btype = btype[1:-1].split(',')
					else:
						btype = [btype]

					if aid2 in atomdict:
						bond = chem.Bond([atomdict[aid], atomdict[aid2]], btype)
						bonds.append(bond)

					bonddict[aid][aid2] = btype

		except Exception, e:
			raise InvalidAdjacencyListException(label)

		# Check consistency using bonddict
		for atom1 in bonddict:
			for atom2 in bonddict[atom1]:
				if atom2 not in bonddict:
					raise InvalidAdjacencyListException(label)
				elif atom1 not in bonddict[atom2]:
					raise InvalidAdjacencyListException(label)
				elif bonddict[atom1][atom2] != bonddict[atom2][atom1]:
					raise InvalidAdjacencyListException(label)


		# Create and return functional group or species
		self.initialize(atoms, bonds)



	def fromCML(self, cmlstr):
		"""
		Convert a string of CML `cmlstr` to a Structure object.
		"""
		cmlstr = cmlstr.replace('\t', '')
		mol = pybel.readstring('cml', cmlstr)
		self.fromOBMol(mol.OBMol)

	def fromInChI(self, inchistr):
		"""
		Convert an InChI string `inchistr` to a Structure object.
		"""
		mol = pybel.readstring('inchi', inchistr)
		self.fromOBMol(mol.OBMol)

	def fromSMILES(self, smilesstr):
		"""
		Convert a SMILES string `smilesstr` to a Structure object.
		"""
		mol = pybel.readstring('smiles', smilesstr)
		self.fromOBMol(mol.OBMol)

	def fromOBMol(self, obmol):
		"""
		Convert an OpenBabel OBMol object `obmol` to a Structure object.
		"""

		atoms = []; bonds = []

		# Add hydrogen atoms to complete molecule if needed
		obmol.AddHydrogens()

		# Iterate through atoms in obmol
		for i in range(0, obmol.NumAtoms()):
			obatom = obmol.GetAtom(i + 1)

			# Use atomic number as key for element
			number = obatom.GetAtomicNum()

			# Process spin multiplicity
			electron = obatom.GetSpinMultiplicity()
			if electron == 0: electron = '0'
			elif electron == 1:	electron = '2S'
			elif electron == 2:	electron = '1'
			elif electron == 3:	electron = '2T'

			atom = chem.Atom(chem.elements[number].symbol, chem.electronStates[electron])
			atoms.append(atom)

			# Add bonds by iterating again through atoms
			for j in range(0, i):
				obatom2 = obmol.GetAtom(j + 1)
				obbond = obatom.GetBond(obatom2)
				if obbond is not None:
					order = ''

					# Process bond type
					if obbond.IsSingle(): order = 'S'
					elif obbond.IsDouble(): order = 'D'
					elif obbond.IsTriple(): order = 'T'
					elif obbond.IsAromatic(): order = 'B'

					bond = chem.Bond([atoms[i], atoms[j]], chem.bondTypes[order])
					bonds.append(bond)

		# Create the graph from the atom and bond lists
		self.initialize(atoms, bonds)

	def toAdjacencyList(self):
		"""
		Convert the structure object to an adjacency list.
		"""

		adjlist = ''

		atoms = self.atoms()

		for i, atom in enumerate(atoms):
			adjlist += str(i+1) + ' '
			if atom.label != '':
				adjlist += atom.label + ' '
			adjlist += atom.atomType.label + ' ' + atom.electronState.label
			for atom2, bond in self.getBonds(atom).iteritems():
				adjlist += ' {' + str(atoms.index(atom2)+1) + ',' + bond.bondType.label + '}'
			adjlist += '\n'

		return adjlist


	def toOBMol(self):
		"""
		Convert a Structure object to an OpenBabel OBMol object.
		"""
		atoms = self.atoms(); bonds = self.bonds()

		obmol = openbabel.OBMol()
		for atom in atoms:
			a = obmol.NewAtom()
			a.SetAtomicNum(atom.atomType.element.number)
		for bond in bonds:
			index1 = atoms.index(bond.atoms[0])
			index2 = atoms.index(bond.atoms[1])
			order = bond.bondType.order
			if order == 1.5: order = 5
			obmol.AddBond(index1+1, index2+1, int(order))

		obmol.AssignSpinMultiplicity(True)

		return obmol

	def toCML(self):
		"""
		Convert a Structure object to CML.
		"""
		mol = pybel.Molecule(self.toOBMol())
		cml = mol.write('cml').strip()
		return '\n'.join([l for l in cml.split('\n') if l.strip()])

	def toInChI(self):
		"""
		Convert a Structure object to an InChI string.
		"""
		# This version does not write a warning to stderr if stereochemistry is undefined
		obmol = self.toOBMol()
		obConversion = openbabel.OBConversion()
		obConversion.SetOutFormat('inchi')
		obConversion.SetOptions('w', openbabel.OBConversion.OUTOPTIONS)
		return obConversion.WriteString(obmol).strip()
		# This version writes a warning to stderr if stereochemistry is undefined
		#mol = pybel.Molecule(self.toOBMol())
		#return mol.write('inchi').strip()

	def toSMILES(self):
		"""
		Convert a Structure object to an SMILES string.
		"""
		mol = pybel.Molecule(self.toOBMol())
		return mol.write('smiles').strip()

	def toXML(self, dom, root):
		"""
		Convert a Structure object to an XML DOM tree.
		"""
		cml = dom.createElement('cml')
		root.appendChild(cml)

		dom2 = xml.dom.minidom.parseString(self.toCML())
		cml.appendChild(dom2.documentElement)

	def simplifyAtomTypes(self):
		"""
		Iterate through the atoms in the structure, setting them to be equal
		to their element.
		"""
		for atom1 in self.atoms():
			# Only works for single atom types, not lists
			if atom1.atomType.__class__ == list:
				continue
			# Skip generic atom types
			if atom1.atomType.label == 'R' or atom1.atomType.label == 'R!H':
				continue
			# Reset atom type to that of element
			atom1.atomType = chem.atomTypes[atom1.atomType.element.symbol]

	def updateAtomTypes(self):
		"""
		Iterate through the atoms in the structure, checking their atom types
		to ensure they are correct (i.e. accurately describe their local bond
		environment) and complete (i.e. are as detailed as possible).
		"""

		# NOTE: Does not yet process CO atom type!

		for atom1 in self.atoms():
			# Only works for single atom types, not lists
			if atom1.atomType.__class__ == list:
				continue
			# Skip generic atom types
			if atom1.atomType.label == 'R' or atom1.atomType.label == 'R!H':
				continue
			# Count numbers of each bond type
			single = 0; double = 0; triple = 0; benzene = 0; carbonyl = False
			for atom2, bond12 in self.getBonds(atom1).iteritems():
				if bond12.isSingle(): single += 1
				elif bond12.isDouble(): double += 1
				elif bond12.isTriple(): triple += 1
				elif bond12.isBenzene(): benzene += 1
				if atom1.isCarbon() and atom2.isOxygen() and bond12.isDouble():
					carbonyl = True

			# Use counts to determine proper atom type
			atomType = atom1.atomType.element.symbol
			if atomType == 'C':
				if triple == 1: atomType = 'Ct'
				elif single == 3 or single == 4: atomType = 'Cs'
				elif double == 2: atomType = 'Cdd'
				elif carbonyl: atomType = 'CO'
				elif double == 1 and (single == 1 or single == 2): atomType = 'Cds'
				elif double == 1: atomType = 'Cd'
				elif benzene == 1 or benzene == 2: atomType = 'Cb'
				elif benzene == 3: atomType = 'Cbf'
			elif atomType == 'O':
				if single == 1 or single == 2: atomType = 'Os'
				elif double == 1: atomType = 'Od'

			# Do nothing if suggested and specified atom types are identical
			if atom1.atomType.label == atomType:
				pass
			# Do nothing if suggested atom type is element
			elif atomType == atom1.atomType.element.symbol or atomType == 'Cd':
				pass
			# Do nothing if specified atom type is 'Cds' or 'Cdd' and suggested is 'Cd'
			elif (atom1.atomType.label == 'Cds' or atom1.atomType.label == 'Cdd') and atomType == 'Cd':
				pass
			# Do nothing if specified atom type is 'Cbf' and suggested is 'Cb'
			elif atom1.atomType.label == 'Cbf' and atomType == 'Cb':
				pass
			# Do nothing if specified atom type is 'Cdd' and suggested is 'CO'
			elif atom1.atomType.label == 'Cdd' and atomType == 'CO':
				pass
			# Make change if specified atom type is element
			elif atom1.atomType.label == atom1.atomType.element.symbol:
				#logging.warning('Changed "' + atom1.atomType.label + '" to "' + atomType + '".')
				atom1.atomType = chem.atomTypes[atomType]
			# Make change if specified atom type is 'Cd' and suggested is 'Cds' or 'Cdd'
			elif atom1.atomType.label == 'Cd' and (atomType == 'Cds' or atomType == 'Cdd' or atomType == 'CO'):
				#logging.warning('Changed "' + atom1.atomType.label + '" to "' + atomType + '".')
				atom1.atomType = chem.atomTypes[atomType]
			# Else print warning
			else:
				logging.warning('Suggested atom type "' + atomType + '" does not match specified atom type "' + atom1.atomType.label + '".')

	def getRadicalCount(self):
		"""
		Get the number of radicals in the structure.
		"""
		radical = 0
		for atom in self.atoms():
			radical += atom.electronState.order
		return radical

	def copy(self):
		"""
		Create a copy of the current Structure.
		"""

		atoms = []; bonds = []
		for atom in self.atoms():
			atoms.append(atom.copy())
		for bond in self.bonds():
			newBond = bond.copy()
			bonds.append(newBond)
			index1 = self.atoms().index(bond.atoms[0])
			index2 = self.atoms().index(bond.atoms[1])
			newBond.atoms = [atoms[index1], atoms[index2]]

		return Structure(atoms, bonds)

	def merge(self, other):
		"""
		Merge two graphs so as to store them in a single Graph object.
		"""

		# Create output graph
		new = Structure()

		# Add atoms to output graph
		for atom in self.atoms():
			new.addAtom(atom)
		for atom in other.atoms():
			new.addAtom(atom)

		# Add bonds to output graph
		for bond in self.bonds():
			new.addBond(bond)
		for bond in other.bonds():
			new.addBond(bond)

		return new

	def split(self):
		"""
		Convert a single Graph object containing two or more unconnected graphs
		into separate graphs.
		"""
		# Create potential output graphs
		new1 = Structure(); new2 = Structure()

		# Add all atoms and bonds to new1
		for atom in self.atoms():
			new1.addAtom(atom)
		for bond in self.bonds():
			new1.addBond(bond)

		# Arbitrarily choose last atom as starting point
		atomsToMove = [ self.atoms()[-1] ]

		# Iterate until there are no more atoms to move
		index = 0
		while index < len(atomsToMove):
			for atom2 in self.getBonds(atomsToMove[index]):
				if atom2 not in atomsToMove:
					atomsToMove.append(atom2)
			index += 1

		# If all atoms are to be moved, simply return new1
		if len(new1.atoms()) == len(atomsToMove):
			return [new1]

		# Copy to new graph
		for atom in atomsToMove:
			new2.addAtom(atom)
		for atom1 in atomsToMove:
			for atom2, bond in new1.getBonds(atom1).iteritems():
				new2.addBond(bond)

		# Remove from old graph
		for bond in new2.bonds():
			new1.removeBond(bond)
		for atom in atomsToMove:
			new1.removeAtom(atom)

		new = [new2]
		new.extend(new1.split())
		return new

	def getAdjacentResonanceIsomers(self):
		"""
		Generate all of the resonance isomers formed by one allyl radical shift.
		"""

		isomers = []

		# Radicals
		if self.getRadicalCount() > 0:
			# Iterate over radicals in structure
			for atom in self.atoms():
				paths = self.findAllDelocalizationPaths(atom)
				for path in paths:

					atom1, atom2, atom3, bond12, bond23 = path

					# Adjust to (potentially) new resonance isomer
					atom1.decreaseFreeElectron()
					atom3.increaseFreeElectron()
					bond12.increaseOrder()
					bond23.decreaseOrder()

					# Make a copy of isomer
					isomer = self.copy()

					# Restore current isomer
					atom1.increaseFreeElectron()
					atom3.decreaseFreeElectron()
					bond12.decreaseOrder()
					bond23.increaseOrder()

					# Append to isomer list if unique
					isomers.append(isomer)

		return isomers

	def findAllDelocalizationPaths(self, atom1):
		"""
		Find all the delocalization paths allyl to the radical center indicated
		by `atom1`. Used to generate resonance isomers.
		"""

		# No paths if atom1 is not a radical
		if atom1.electronState.order <= 0:
			return []

		# Find all delocalization paths
		paths = []
		for atom2, bond12 in self.getBonds(atom1).iteritems():
			# Vinyl bond must be capable of gaining an order
			if bond12.canIncreaseOrder():
				for atom3, bond23 in self.getBonds(atom2).iteritems():
					# Allyl bond must be capable of losing an order without
					# breaking
					if atom1 is not atom3 and bond23.canDecreaseOrder():
						paths.append([atom1, atom2, atom3, bond12, bond23])
		return paths

	def clearLabeledAtoms(self):
		"""
		Remove the labels from all atoms in the structure.
		"""
		for atom in self.atoms():
			atom.label = ''

	def containsLabeledAtom(self, label):
		"""
		Return :data:`True` if the structure contains an atom with the label
		`label` and :data:`False` otherwise.
		"""
		for atom in self.atoms():
			if atom.label == label: return True
		return False

	def getLabeledAtom(self, label):
		"""
		Return the atoms in functional group structure that are labeled, i.e.
		the center atoms in the structure.
		"""
		for atom in self.atoms():
			if atom.label == label: return atom
		return None

	def getLabeledAtoms(self):
		"""
		Return the atoms in functional group structure that are labeled, i.e.
		the center atoms in the structure.
		"""
		atoms = {}
		for atom in self.atoms():
			if atom.isCenter(): atoms[atom.label] = atom
		return atoms

################################################################################

if __name__ == '__main__':

	structure1 = Structure()
	atom1 = structure1.addAtom(chem.Atom('C', '0'))
	atom2 = structure1.addAtom(chem.Atom('C', '0'))
	atom3 = structure1.addAtom(chem.Atom('C', '0'))
	atom4 = structure1.addAtom(chem.Atom('C', '0'))
	atom5 = structure1.addAtom(chem.Atom('C', '0'))
	atom6 = structure1.addAtom(chem.Atom('C', '0'))
	bond1 = structure1.addBond(chem.Bond([atom1, atom2], 'S'))
	bond2 = structure1.addBond(chem.Bond([atom2, atom3], 'S'))
	bond3 = structure1.addBond(chem.Bond([atom3, atom4], 'S'))
	bond4 = structure1.addBond(chem.Bond([atom4, atom5], 'S'))
	bond5 = structure1.addBond(chem.Bond([atom5, atom6], 'S'))

	structure2 = Structure()
	atom1 = structure2.addAtom(chem.Atom('C', '0'))
	atom2 = structure2.addAtom(chem.Atom('C', '0'))
	atom3 = structure2.addAtom(chem.Atom('C', '0'))
	atom4 = structure2.addAtom(chem.Atom('C', '0'))
	bond1 = structure2.addBond(chem.Bond([atom1, atom2], 'S'))
	bond2 = structure2.addBond(chem.Bond([atom2, atom3], 'S'))
	bond3 = structure2.addBond(chem.Bond([atom3, atom4], 'S'))

	for i in range(10000):
		match, map21List, map12List = structure1.findSubgraphIsomorphisms(structure2)