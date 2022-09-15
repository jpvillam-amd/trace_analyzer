class Node:
    def __init__(self, traceEvent):

        self.name = traceEvent["name"]
        self.start = int(traceEvent["ts"])
        self.end = self.start + int(traceEvent["dur"])
        self.children = []
        self.parent = None
        self.is_kernel = traceEvent.setdefault("cat", "") in (
            "Kernel",
            "KernelExecution",
            "FillBuffer",
        )
        self.traceEvent = traceEvent

    def isInside(self, node) -> bool:
        if isinstance(node, int):
            return node >= self.start and node <= self.end
        else:
            return node.start >= self.start and node.end <= self.end

    def __str__(self):
        s = f" {self.name} {self.start} {self.end}->"
        for child in self.children:
            s = s + str(child)
        return s

    def addChild(self, node):

        if self.isInside(node):
            for child in self.children:
                if child.addChild(node):
                    return True
            node.parent = self
            # Does the node need to consume some children
            children_to_remove = []
            for child in self.children:
                if node.isInside(child):
                    # GobleGobble
                    child.parent = node
                    node.children.append(child)
                    # Can't self.children.remove(child) messes with the iteration..
                    children_to_remove.append(child)
            for child in children_to_remove:
                self.children.remove(child)
            self.children.append(node)
            return True
        else:
            return False

    def search(self, time: int):
        if self.isInside(time):
            for child in self.children:
                if child.isInside(time):
                    return child.search(time)
            return self
        else:
            print("XXX: Searching for something outside iteration")

    def toList(self):
        r_list = []
        r_list.append(self)
        for child in self.children:
            r_list.extend(child.toList())
        return r_list

    def getNames(self, no_kernels, name_changer):
        r_list = []
        if self.is_kernel:
            return r_list
        name = self.name if name_changer is None else name_changer(self.name)
        r_list.append(name)
        for child in self.children:
            r_list.extend(child.getNames(no_kernels, name_changer))
        return r_list


class Graph:
    def __init__(self):
        tn = Node(
            {
                "name": "top_node",
                "ts": "0",
                "dur": "0",
                "desc": "top_node",
                "cat": "top node",
                "args": {"desc": "top node"},
            }
        )
        tn.end = float("inf")
        self.top_node = tn

    def __str__(self):
        return "Top Node: " + str(self.top_node)

    def addNode(self, node):
        if self.top_node is None:
            self.top_node = node
        else:
            self.top_node.addChild(node)

    def search(self, time):
        return self.top_node.search(time)

    def toList(self):
        r_list = []
        r_list.extend(self.top_node.toList())
        return r_list

    def getNames(self, no_kernels=False, name_changer=None):
        r_list = []
        r_list.extend(self.top_node.getNames(no_kernels, name_changer))
        return r_list
