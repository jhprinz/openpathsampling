__author__ = 'jan-hendrikprinz'

class TreeMixin(object):
    """
    A mixin that provides basic tree handling.

    A tree is basically a node with children of the same type. The mixin
    requires to implement `.subnodes` to contain a list of children.

    The `__contains__` operator requires `_default_match` to be implemented.
    Otherwise is defaults to a comparison between two elements.
    """

    @staticmethod
    def _indent(s):
        spl = s.split('\n')
        spl = [' |  ' + p if p[0] == ' ' else ' +- ' + p for p in spl]
        return '\n'.join(spl)

    @property
    def _subnodes(self):
        return []

    def __iter__(self):
        yield self
        for subchange in self._subnodes:
            for change in subchange:
                yield change

    def __getitem__(self, item):
        """
        Return the n-th subchange

        Returns
        -------
        PathMoveChange
            the n-th subchange if this PathMoveChange uses underlying changes
        """
        if type(item) is int:
            return self._subnodes[item]

        if type(item) is list:
            # this is assumed to be a tree
            if self._default_match(item[0], self):
                if len(item) > 1:
                    for ch in self._subnodes:
                        r = ch[item[1]]
                        if r is not None:
                            return r
                    return None
                else:
                    return self
            else:
                return None


    def __reversed__(self):
        for subchange in self._subnodes:
            for change in reversed(subchange):
                yield change

        yield self

    def __len__(self):
        """
        Returns the total number of Changes mad in a move.

        Returns
        -------
        int
            the number of (Sub)PathMoveChanges in this PathMoveChange

        """
        if self._len is None:
            self._len = len(list(iter(self)))

        return self._len

    def key(self, change):
        tree = self.keytree()
        return [leave for leave in tree if leave[1] is change ][0][0]

    @classmethod
    def _check_tree(cls, tree, branch, match):
        WILDCATS = {
            '*' : lambda s : slice(0,None),
            '.' : lambda s : slice(1,2),
            '?' : lambda s : slice(0,2),
            ':' : lambda s : slice(*map(int, s.split(':')))
        }
        MATCH_ONE = ['.', '?', '*']

        if branch[0] not in MATCH_ONE and not match(tree[0], branch[0]):
            return False
        else:
            if len(branch) > 1:
                sub = branch[1]
                sub_branch = [branch[0]] + branch[2:]
                if type(sub) is str:
                    region = None
                    for wild in WILDCATS:
                        if wild in sub:
                            region = WILDCATS[wild](sub)
                            break

                    if region is None:
                        raise ValueError('Parse error. ONLY ' + str(WILDCATS.values()) + ' as wildcats allowed.')

                    if region.start < len(tree):
                        # check that there are enough children to match
                        for left in range(*region.indices(len(tree))):

                            sub_tree = [tree[0]] + tree[1+left:]
                            if cls._check_tree(sub_tree, sub_branch, match):
                                return True

                    return False
                else:
                    if len(tree) > 1:
                        if not cls._check_tree(tree[1], sub, match):
                            return False
                        else:
                            # go to next sub in branch
                            if len(branch) > 2:
                                if len(tree) > 2:
                                    return cls._check_tree([tree[0]] + tree[2:], sub_branch, match)
                                else:
                                    return False
                    else:
                        # still branch, but no more tree
                        return False

        return True

    def _check_head_node(self, items):
        tree = self.tree()
        return self._check_tree(tree, items, self._default_match)

    @staticmethod
    def _default_match(original, test):
        if original == test:
            return True
        else:
            return False

    def __contains__(self, item):
        """
        Check if a pathmover, pathmovechange or a tree is in self

        The tree structure is as follows

        1. A tree consists of nodes
        2. Each node can have zero, one or more children
        3. Each child is a node itself

        The tree structure in openpathsampling is expressed as

        1. The tree structure is given as a nested list.
        2. The first element in the list is the node
        3. Element 2 to N are the children.
        4. Children are always wrapped in brackets
        5. An element can be a PathMover instance or PathMoveChange instance

        node = [element, [child1], [child2], ... ]

        A tree can be a subtree if the subtree (always starting from the top)
        fits on top of the tree to match. Here child nodes are ignored as long
        as the mask of the subtree fits.

        In searching wildcats are allowed. This works

        1. slice(start, end) means an a number of arbitrary children between
            start and end-1
        2. '*' means an arbitrary number of arbitrary children. Equal to slice(0, None)
        3. None or '.' means ONE arbitrary child. Equal to slice(1,2)
        4. '?' means ONE or NONE arbitrary child. Equal to slice(0,2)

        Examples
        --------
        >>> tree1 = [mover1, [mover2]]
        >>> tree2 = [mover1, [mover2], [mover3]]
        >>> tree3 = [mover1, [mover2], [mover4, [mover5]]]
        >>> tree4 = []

        Parameters
        ----------
        item : PathMover, PathMoveChange, PathMoveTree

        """
        if type(item) is list:
            return self._check_head_node(item)

            # Disable checking for submoves for now

            # the head node did not fit so continue trying subnodes
#            for sub in self.subnodes:
#                if item in sub:
#                    return True

        return False

    def tree(self):
        return [self] + [ ch.tree() for ch in self._subnodes]

    def map_tree(self, fnc):
        """
        Apply a function to each node and return the tree

        Parameters
        ----------
        fnc : function(pathmovechange, args, kwargs)
            the function run at each pathmovechange node. It is given the node
            and the optional (fixed) parameters
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        tree (fnc(node, **kwargs))
            nested list of the results of the map
        """
        return [fnc(self)] + [ ch.map_tree(fnc) for ch in self._subnodes]

    @property
    def identifier(self):
        return hex(id(self))

    def keytree(self):
        path = [self.identifier]

        result = list()
        result.append( ( path, self ) )
        mp = []
        for sub in self._subnodes:
            subtree = sub.keytree()
            result.extend([ ( path + mp + [m[0]], m[1] ) for m in subtree ])
            mp.extend([subtree[-1][0]])

        return result

    def map_post_order(self, fnc, **kwargs):
        """
        Traverse the tree in post-order applying a function

        This traverses the underlying tree and applies the given function at
        each node returning a list of the results. Post-order means
        that subnodes are called BEFORE the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, kwargs)
            the function run at each node. It is given the node and the
            optional (fixed) parameters
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list (fnc(node, **kwargs))
            flattened list of the results of the map

        Notes
        -----
        This uses the same order as `reversed()`

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """
        return [ fnc(node, **kwargs) for node in reversed(self) ]

    def depth_post_order(self, fnc, level=0, **kwargs):
        """
        Traverse the tree in post-order applying a function with depth

        This traverses the underlying tree and applies the given function at
        each node returning a list of the results. Post-order means
        that subnodes are called BEFORE the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, **kwargs)
            the function run at each node. It is given the node and the
            optional (fixed) parameters
        level : int
            the initial level
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list of tuple(level, func(node, **kwargs))
            flattened list of tuples of results of the map. First part of
            the tuple is the level, second part is the function result.

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """

        output = list()
        for mp in self._subnodes:
            output.extend(mp.depth_post_order(fnc, level + 1, **kwargs))
        output.append((level, fnc(self, **kwargs)))

        return output

    def map_pre_order(self, fnc, **kwargs):
        """
        Traverse the tree in pre-order applying a function

        This traverses the underlying tree applies the given function at
        each node returning a list of the results. Pre-order means
        that subnodes are called AFTER the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, **kwargs)
            the function run at each node. It is given the node and the
            optional parameters
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list (fnc(node, **kwargs))
            flattened list of the results of the map

        Notes
        -----
        This uses the same order as `iter()`

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """
        return [ fnc(node, **kwargs) for node in iter(self) ]

    def depth_pre_order(self, fnc, level=0, **kwargs):
        """
        Traverse the tree of node in pre-order applying a function

        This traverses the underlying tree applies the given function at
        each node returning a list of the results. Pre-order means
        that subnodes are called AFTER the node itself is evaluated.

        Parameters
        ----------
        fnc : function(node, **kwargs)
            the function run at each node. It is given the node and the
            optional parameters
        level : int
            the initial level
        kwargs : named arguments
            optional arguments added to the function

        Returns
        -------
        list of tuple(level, fnc(node, **kwargs))
            flattened list of tuples of results of the map. First part of
            the tuple is the level, second part is the function result.

        See also
        --------
        map_pre_order, map_post_order, level_pre_order, level_post_order
        """

        output = list()
        output.append((level, fnc(self, **kwargs)))

        for mp in self._subnodes:
            output.extend(mp.depth_pre_order(fnc, level + 1, **kwargs))

        return output