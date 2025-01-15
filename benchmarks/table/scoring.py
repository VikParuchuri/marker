""""
TEDS Code Adapted from https://github.com/ibm-aur-nlp/EDD
"""

import distance
from apted import APTED, Config
from apted.helpers import Tree
from lxml import html
from collections import deque

def wrap_table_html(table_html:str)->str:
    return f'<html><body>{table_html}</body></html>'

class TableTree(Tree):
    def __init__(self, tag, colspan=None, rowspan=None, content=None, *children):
        self.tag = tag
        self.colspan = colspan
        self.rowspan = rowspan
        self.content = content

        # Sets self.name and self.children
        super().__init__(tag, *children)

    def bracket(self):
        """Show tree using brackets notation"""
        if self.tag == 'td':
            result = '"tag": %s, "colspan": %d, "rowspan": %d, "text": %s' % \
                     (self.tag, self.colspan, self.rowspan, self.content)
        else:
            result = '"tag": %s' % self.tag
        for child in self.children:
            result += child.bracket()
        return "{{{}}}".format(result)

class CustomConfig(Config):
    @staticmethod
    def maximum(*sequences):
        return max(map(len, sequences))

    def normalized_distance(self, *sequences):
        return float(distance.levenshtein(*sequences)) / self.maximum(*sequences)

    def rename(self, node1, node2):
        if (node1.tag != node2.tag) or (node1.colspan != node2.colspan) or (node1.rowspan != node2.rowspan):
            return 1.
        if node1.tag == 'td':
            if node1.content or node2.content:
                return self.normalized_distance(node1.content, node2.content)
        return 0.

def tokenize(node):
    """
    Tokenizes table cells
    """
    global __tokens__
    __tokens__.append('<%s>' % node.tag)
    if node.text is not None:
        __tokens__ += list(node.text)
    for n in node.getchildren():
        tokenize(n)
    if node.tag != 'unk':
        __tokens__.append('</%s>' % node.tag)
    if node.tag != 'td' and node.tail is not None:
            __tokens__ += list(node.tail)

def tree_convert_html(node, convert_cell=False, parent=None):
    """
    Converts HTML tree to the format required by apted
    """
    global __tokens__
    if node.tag == 'td':
        if convert_cell:
            __tokens__ = []
            tokenize(node)
            cell = __tokens__[1:-1].copy()
        else:
            cell = []
        new_node = TableTree(node.tag,
                             int(node.attrib.get('colspan', '1')),
                             int(node.attrib.get('rowspan', '1')),
                             cell, *deque())
    else:
        new_node = TableTree(node.tag, None, None, None, *deque())
    if parent is not None:
        parent.children.append(new_node)
    if node.tag != 'td':
        for n in node.getchildren():
            tree_convert_html(n, convert_cell, new_node)
    if parent is None:
        return new_node

def similarity_eval_html(pred, true, structure_only=False):
    """
    Computes TEDS score between the prediction and the ground truth of a given samples
    """
    pred, true = html.fromstring(pred), html.fromstring(true)
    if pred.xpath('body/table') and true.xpath('body/table'):
        pred = pred.xpath('body/table')[0]
        true = true.xpath('body/table')[0]
        n_nodes_pred = len(pred.xpath(".//*"))
        n_nodes_true = len(true.xpath(".//*"))
        tree_pred = tree_convert_html(pred, convert_cell=not structure_only)
        tree_true = tree_convert_html(true, convert_cell=not structure_only)
        n_nodes = max(n_nodes_pred, n_nodes_true)
        distance = APTED(tree_pred, tree_true, CustomConfig()).compute_edit_distance()
        return 1.0 - (float(distance) / n_nodes)
    else:
        return 0.0

