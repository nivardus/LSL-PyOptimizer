#    (C) Copyright 2015-2021 Sei Lisa. All rights reserved.
#
#    This file is part of LSL PyOptimizer.
#
#    LSL PyOptimizer is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    LSL PyOptimizer is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with LSL PyOptimizer. If not, see <http://www.gnu.org/licenses/>.

# Dead Code Removal optimization

from lslopt import lslfuncs
from lslopt.lslcommon import nr
from lslopt.strutil import xrange

class deadcode(object):

    def MarkReferences(self, node):
        """Marks each node it passes through as executed (X), and each variable
        as read (R) (with count) and/or written (W) (with node where it is, or
        False if written more than once) as appropriate. Traces execution to
        determine if any part of the code is never executed.
        """
        # The 'X' key, when present, indicates whether a node is executed.
        # Its value means whether this instruction will proceed to the next
        # (True: it will; False: it won't).
        if hasattr(node, 'X'):
            return node.X # branch already analyzed

        nt = node.nt
        child = node.ch

        # Control flow statements

        if nt == 'STSW':
            node.X = False # Executed but path-breaking.
            sym = self.symtab[0][node.name]
            if not hasattr(self.tree[sym['Loc']], 'X'):
                self.MarkReferences(self.tree[sym['Loc']])

            return False

        if nt == 'JUMP':
            node.X = False # Executed but path-breaking.
            sym = self.symtab[node.scope][node.name]
            if 'R' in sym:
                sym['R'] += 1
            else:
                sym['R'] = 1
            return False

        if nt == 'RETURN':
            node.X = False # Executed but path-breaking.
            if child:
                self.MarkReferences(child[0])
            return False

        if nt == 'IF':
            # "When you get to a fork in the road, take it."
            node.X = None # provisional value, refined later
            self.MarkReferences(child[0])
            condnode = child[0]
            if condnode.nt == 'CONST':
                if lslfuncs.cond(condnode.value):
                    # TRUE - 'then' branch always executed.
                    node.X = self.MarkReferences(child[1])
                    return node.X
                elif len(child) == 3:
                    # FALSE - 'else' branch always executed.
                    node.X = self.MarkReferences(child[2])
                    return node.X
                # else fall through
            else:
                cont = self.MarkReferences(child[1])
                if len(child) == 3:
                    if not cont:
                        cont = self.MarkReferences(child[2])
                        node.X = cont
                        return cont
                    self.MarkReferences(child[2])
            node.X = True
            return True

        if nt == 'WHILE':
            node.X = None # provisional value, refined later
            self.MarkReferences(child[0])

            if child[0].nt == 'CONST':
                if lslfuncs.cond(child[0].value):
                    # Infinite loop - unless it returns, it stops
                    # execution. But it is executed itself.
                    self.MarkReferences(child[1])
                    node.X = False
                    return node.X
                # else the inside isn't executed at all, so don't mark it
            else:
                self.MarkReferences(child[1])
            node.X = True
            return True

        if nt == 'DO':
            node.X = None # provisional value, refined later
            if not self.MarkReferences(child[0]):
                node.X = False
                return False
            self.MarkReferences(child[1])
            # It proceeds to the next statement unless it's an infinite loop
            node.X = not (child[1].nt == 'CONST' and lslfuncs.cond(child[1].value))
            return node.X

        if nt == 'FOR':
            node.X = None # provisional value, refined later
            self.MarkReferences(child[0])
            self.MarkReferences(child[1])
            if child[1].nt == 'CONST':
                if lslfuncs.cond(child[1].value):
                    # Infinite loop - unless it returns, it stops
                    # execution. But it is executed itself.
                    node.X = False
                    self.MarkReferences(child[3])
                    self.MarkReferences(child[2]) # this can't stop execution
                    return node.X
                # else the body and the iterator aren't executed at all, so
                # don't mark them
                node.X = True
            else:
                node.X = True
                self.MarkReferences(child[3])
                self.MarkReferences(child[2])
            # Mark the EXPRLIST as always executed, but not the subexpressions.
            # That forces the EXPRLIST (which is a syntactic requirement) to be
            # kept, while still simplifying the contents properly.
            child[2].X = True
            return True

        if nt == '{}':
            # Go through each statement in turn. If one stops execution,
            # continue reading until either we find a used label (and resume
            # execution) or reach the end (and return False). Otherwise return
            # True.

            continues = True
            node.X = None # provisional
            for stmt in child:
                if continues or stmt.nt == '@':
                    continues = self.MarkReferences(stmt)
            node.X = continues
            return continues

        if nt == 'FNCALL':
            node.X = None # provisional
            sym = self.symtab[0][node.name]

            fdef = self.tree[sym['Loc']] if 'Loc' in sym else None
            for idx in xrange(len(child)-1, -1, -1):
                # Each element is a "write" on the callee's parameter.
                # E.g. f(integer a, integer b) { f(2,3); } means 2, 3 are
                # writes to a and b.
                # This has been eliminated, as it causes more trouble than
                # it fixes.
                self.MarkReferences(child[idx])
                if fdef is not None:
                    psym = self.symtab[fdef.pscope][fdef.pnames[idx]]
                    #if 'W' in psym:
                    #    psym['W'] = False
                    #else:
                    #    psym['W'] = child[idx]
                    psym['W'] = False

            if 'Loc' in sym:
                if not hasattr(self.tree[sym['Loc']], 'X'):
                    self.MarkReferences(self.tree[sym['Loc']])
                node.X = self.tree[sym['Loc']].X
            else:
                node.X = 'stop' not in sym
            # Note that JUMP analysis is incomplete. To do it correctly, we
            # should follow the jump right to its destination, in order to know
            # if that branch leads to a RETURN or completely stops the event.
            # With our code structure, following the JUMP is unfeasible.
            # For that reason, we can't track whether a branch ends in RETURN
            # or in something more powerful like a script reset, in order to
            # propagate it through the function definition to the caller.
            #
            # In practice, this means that the caller can't distinguish this:
            #     fn() { return; }
            # from this:
            #     fn() { llResetScript(); }
            # and therefore, invocations of the function that are followed by
            # code can't know whether that code is dead or not.
            #
            # What does that have to do with jumps? Well, imagine this:
            #     fn(integer x) { if (x) jump x1; else jump x2;
            #                     @x1; return; @x2; llResetScript(); }
            # What of the branches of if() is taken, depends on where the jumps
            # lead to. Assuming the last one always is wrong, because it would
            # mark in the caller code that may execute, as dead, e.g. here:
            #     fn2() { fn(); x = 1; }


            return node.X

        if nt == 'DECL':
            sym = self.symtab[node.scope][node.name]
            if child is not None:
                sym['W'] = child[0]
            else:
                sym['W'] = nr(nt='CONST', t=node.t,
                    value=self.DefaultValues[node.t])

            node.X = True
            if child is not None:
                if hasattr(child[0], 'orig'):
                    orig = child[0].orig
                    self.MarkReferences(orig)
                    child[0].X = orig.X
                    if orig.nt == 'LIST':
                        # Add fake writes to variables used in list elements in
                        # 'orig', so they don't get deleted (Issue #3)
                        for subnode in orig.ch:
                            if subnode.nt == 'IDENT':
                                # can only happen in globals
                                assert subnode.scope == 0
                                sym = self.symtab[0][subnode.name]
                                sym['W'] = False
                                self.tree[sym['Loc']].X = True
                            elif subnode.nt in ('VECTOR', 'ROTATION'):
                                for sub2node in subnode.ch:
                                    if sub2node.nt == 'IDENT':
                                        # can only happen in globals
                                        assert sub2node.scope == 0
                                        sym = self.symtab[0][sub2node.name]
                                        sym['W'] = False
                                        self.tree[sym['Loc']].X = True
                else:
                    self.MarkReferences(child[0])
            return True

        # ---- Starting here, all node types return through the bottom
        #      (except '=').

        node.X = None # provisional
        if nt in self.assign_ops or nt in ('--V', '++V', 'V++', 'V--'):
            ident = node.ch[0]
            if ident.nt == 'FLD':
                ident = ident.ch[0]
            assert ident.nt == 'IDENT'
            sym = self.symtab[ident.scope][ident.name]
            if ident.scope == 0:
                # Mark the global first.
                self.MarkReferences(self.tree[sym['Loc']])
            # In any case, this is at least the second write, so mark it as such
            # (SSA would be a plus for this to be optimal)
            sym['W'] = False

            if nt == '=':
                # Prevent the first node from being mistaken as a read, by
                # recursing only on the RHS node.
                self.MarkReferences(child[1])
                node.X = True
                return True

        elif nt == 'FLD':
            # Mark this variable as referenced by a Field (recursing will mark
            # the ident as read later)
            self.symtab[child[0].scope][child[0].name]['Fld'] = True

        elif nt == 'IDENT':
            sym = self.symtab[node.scope][node.name]
            # Mark global if it's one.
            if 'W' not in sym and node.scope == 0:
                self.MarkReferences(self.tree[sym['Loc']])
            # Increase read counter
            if 'R' in sym:
                sym['R'] += 1
            else:
                sym['R'] = 1

        node.X = True
        if child is not None:
            for subnode in child:
                self.MarkReferences(subnode)

        return True

    def OKtoRemoveSymbol(self, curnode):
        """If the given node's name must be simplified, that is, replaced or
        deleted (deleted if declaration, replaced if identifier), it returns
        the symbol table entry. Otherwise it returns False.
        """
        # 'W':False means written more than once, i.e. not only in the
        # declaration. Variables written more than once can't be
        # simplified by this code.

        # If not written more than once:
        #   For expressions:
        #   - Remove expressions read only once, replacing the value, but only
        #     if the readers are not fields of vectors or rotations, and if
        #     they are side-effect free.
        #   For constants:
        #   - Remove lists, vectors and rotations read only once.
        #   - Floats are removed if their value has no decimals or if
        #     used no more than N times (for some N).
        #   - Strings, keys and integers are just removed.
        sym = self.symtab[curnode.scope][curnode.name]

        if 'R' not in sym:
            return sym  # if not used, it can be removed

        # Event parameters do not have 'W' in sym.
        if 'W' not in sym:
            return False

        if sym['W'] is not False:

            node = sym['W']
            nt = node.nt

            # This screws up swaps. See
            # unit_tests/regression.suite/aggressive-local-removal.lsl
            # It can't be done without a reliable CFG-based method (SSA or
            # the like).

#            while nt == 'IDENT':
#                # Follow the chain of identifiers all the way to the original
#                if self.symtab[node.scope][node.name].get('W', False) is False:
#                    return sym
#                sym = self.symtab[node.scope][node.name]
#                node = sym['W']
#                nt = node.nt

            if nt == 'CONST':
                tcurnode = curnode.t
                if tcurnode in ('integer', 'string', 'key'):
                    return sym

                if tcurnode == 'float':
                    if sym['R'] <= 3 or type(node.value) == int:
                        return sym
                elif tcurnode == 'vector' \
                     or tcurnode == 'list' and len(node.value) <= 3:
                    if sym['R'] <= 1:
                        return sym
                elif tcurnode == 'rotation' \
                     or tcurnode == 'list' and len(node.value) <= 4:
                    if sym['R'] <= 1:
                        return sym
                return False

            # To replace expressions, they MUST be side-effect free, or they
            # will be executed at a different time.
            # Also, we can't safely replace expressions unless shrinknames is
            # active. shrinknames assigns a different identifier to each
            # variable, which avoids conflicts. Consider this scenario:
            #  integer i=2;
            #  default{state_entry(){integer j=i+1; integer i=4; llSleep(i+j);}}
            # Replacing j with i+1 in llOwnerSay will produce wrong code because
            # the name i is redefined after j is assigned. shrinknames prevents
            # that.
            # FIXME: shrinknames and SEF are not enough guarantee. This needs
            # analyzing a control flow graph.
            #if not self.shrinknames or not node.SEF:
            if True or not self.shrinknames or not node.SEF:
                return False

            if nt not in ('VECTOR', 'ROTATION'):
                # If it's an expression and the reference is to a field, we
                # can't simplify. Consider e.g.:
                #    vector v = llGetVel(); llOwnerSay((string)v.z);
                # However, if it's a field coming from a Vector or Rotation
                # expression, we can embed the corresponding component, e.g.
                #    vector v = <i+1, i+2, i+3>; llOwnerSay((string)v.y);
                # can be replaced with: llOwnerSay((string)((float)(i+2)));

                if 'Fld' in sym:
                    return False

            if sym['R'] == 1:
                return sym

        return False

    def CleanNode(self, curnode, isFnDef = False):
        """Recursively checks if the children are used, deleting those that are
        not.
        """
        if curnode.ch is None or (curnode.nt == 'DECL'
                                  and curnode.scope == 0):
            return
        # NOTE: Should not depend on 'Loc', since the nodes that are the
        # destination of 'Loc' are renumbered as we delete stuff from globals.

        index = int(curnode.nt in self.assign_ops) # don't recurse into lvalues

        while index < len(curnode.ch):
            node = curnode.ch[index]

            if not hasattr(node, 'X'):
                deleted = curnode.ch[index]
                # Don't delete the child of a RETURN statement!
                if curnode.nt == 'RETURN':
                    pass
                # If it's a RETURN as the last statement of a block in a
                # function definition, don't delete it (a hacky workaround for
                # issue #14).
                elif (deleted.nt == 'RETURN' and index == len(curnode.ch) - 1
                      and isFnDef):
                    pass
                else:
                    del curnode.ch[index]
                    if deleted.nt == 'JUMP':
                        # Decrease label reference count
                        scope = deleted.scope
                        name = deleted.name
                        assert self.symtab[scope][name]['ref'] > 0
                        self.symtab[scope][name]['ref'] -= 1
                    continue

            nt = node.nt

            if nt == 'DECL':
                if self.OKtoRemoveSymbol(node):
                    if not node.ch or node.ch[0].SEF:
                        del curnode.ch[index]
                        continue
                    node = curnode.ch[index] = nr(nt='EXPR', t=node.t,
                        ch=[self.Cast(node.ch[0], node.t)])

            elif nt == 'FLD':
                sym = self.OKtoRemoveSymbol(node.ch[0])
                if sym:
                    value = sym['W']
                    # Mark as executed, so it isn't optimized out.
                    value.X = True
                    fieldidx = 'xyzs'.index(node.fld)
                    if value.nt == 'CONST':
                        value = value.value[fieldidx]
                        value = nr(nt='CONST', X=True, SEF=True,
                            t=self.PythonType2LSL[type(value)], value=value)
                        value = self.Cast(value, 'float')
                        SEF = True
                    else: # assumed VECTOR or ROTATION per OKtoRemoveSymbol
                        SEF = value.SEF
                        value = self.Cast(value.ch[fieldidx], 'float')
                    # Replace it
                    node = curnode.ch[index] = value
                    node.SEF = SEF

            elif nt == 'IDENT':
                sym = self.OKtoRemoveSymbol(node)
                if sym:
                    # Mark as executed, so it isn't optimized out.
                    # Make shallow copy.
                    # TODO: Should the copy be a deep copy?
                    assert sym.get('W', False) is not False
                    new = sym['W'].copy()
                    if hasattr(new, 'orig'):
                        del new.orig

                    new.X = True

                    # this part makes no sense?
                    #new.SEF = sym['W'].SEF

                    if new.t != node.t:
                        new = self.Cast(new, node.t)
                    curnode.ch[index] = node = new
                    # Delete orig if present, as we've eliminated the original
                    #if hasattr(sym['W'], 'orig'):
                    #    del sym['W'].orig

            elif nt in self.assign_ops:
                ident = node.ch[0]
                if ident.nt == 'FLD':
                    ident = ident.ch[0]
                sym = self.OKtoRemoveSymbol(ident)
                if sym:
                    node = curnode.ch[index] = self.Cast(node.ch[1], node.t)

            elif nt in ('IF', 'WHILE', 'DO', 'FOR'):
                # If the mandatory statement is to be removed, replace it
                # with a ; to prevent leaving the statement empty.
                child = node.ch
                idx = 3 if nt == 'FOR' else 0 if nt == 'DO' else 1
                if not hasattr(child[idx], 'X'):
                    child[idx] = nr(nt=';', t=None, X=True, SEF=True)
                if nt == 'DO' and not hasattr(child[1],'X'):
                    # Mandatory condition but not executed - replace
                    child[1] = nr(nt='CONST', X=True, SEF=True, t='integer',
                        value=0)

            self.CleanNode(node, isFnDef = (curnode.nt == 'FNDEF'))
            index += 1


    def RemoveDeadCode(self):
        """Simple reference-based dead code removal. It also performs a
        simplified form of constant propagation, taking advantage of the fact
        that it analyzes the code flow.
        """
        # TODO: Converting to SSA first would facilitate DCR.
        # The SSA should be followed by constant and expression propagation,
        # then constant folding and then dead code removal.

        # Start at state default and mark everything referenced from there.
        # At the end, unreferenced globals and states will be removed.
        # We assume all events in a state are executed.
        #
        # This may not be the case, e.g. a target()/no_target() without
        # llTarget, sensor()/no_sensor() without llSensor(), listen() without
        # llListen, timer without llSetTimerEvent, etc. but we're not that
        # sophisticated (yet).

        # TODO: Inlining of functions that are a single 'return' line.

        if lslfuncs.lslcommon.IsCalc:
            # Do nothing if in calculator mode (there's no default event
            # and it crashes without this)
            return

        statedef = self.tree[self.symtab[0]['default']['Loc']]
        assert statedef.nt == 'STDEF' and statedef.name == 'default'

        self.MarkReferences(statedef)

        # Track removal of global lines, to reasign locations later.
        LocMap = list(range(len(self.tree)))

        GlobalDeletions = []

        # Perform the removal
        idx = 0
        while idx < len(self.tree):
            # Globals are special.
            # We need to track the locations too.
            node = self.tree[idx]

            delete = False
            if not hasattr(node, 'X'):
                delete = True
            elif node.nt == 'DECL':
                delete = self.OKtoRemoveSymbol(node)

            if delete:
                # Mark the symbol for later deletion from symbol table.
                # We can't remove it here because there may be more references
                # that we will remove in CleanNode later, that hold the
                # original value.
                if node.nt == 'DECL' or node.nt == 'STDEF':
                    GlobalDeletions.append(node.name)
                del self.tree[idx]
                del LocMap[idx]
            else:
                idx += 1
                self.CleanNode(node)

        # Remove the globals now.
        for name in GlobalDeletions:
            del self.symtab[0][name]

        del GlobalDeletions

        # Reassign locations
        for name in self.symtab[0]:
            if name != -1:
                sym = self.symtab[0][name]
                if 'Loc' in sym:
                    try:
                        sym['Loc'] = LocMap.index(sym['Loc'])
                    except ValueError:
                        # Subtree deleted - delete the Loc
                        del sym['Loc']
