class Node:
    def __init__(self, traceEvent):

        self.name = traceEvent["name"]
        self.start = int(traceEvent["ts"])
        self.end = self.start + int(traceEvent["dur"])
        self.duration = int(traceEvent["dur"])
        self.children = []
        self.parent = None
        self.cat = traceEvent.setdefault("cat", "")
        self.is_kernel = traceEvent.setdefault("cat", "") in (
            "Kernel",
            "KernelExecution",
            "FillBuffer",
            "Memset",
            "kernel",
            "Memcpy",
            "gpu_memcpy",
            "gpu_memset",
        )
        self.is_kernel_launch = self.name in (
            "hipExtModuleLaunchKernel",
            "hipLaunchKernel",
            "cudaLaunchKernel",
        )
        self.traceEvent = traceEvent

    def isInside(self, node) -> bool:
        if isinstance(node, int):
            return node >= self.start and node < self.end
        else:
            return node.start >= self.start and node.end <= self.end

    def __str__(self):
        s = f" {self.name} {self.start} {self.end}: ("
        for child in self.children:
            s = s + str(child)
        return s + ")"

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

    def nameSearch(self, name: str):
        r_list = []
        if name in self.name:
            r_list.append(self)
        for child in self.children:
            r_list.extend(child.nameSearch(name))
        return r_list

    def toList(self):
        r_list = []
        r_list.append(self)
        for child in self.children:
            r_list.extend(child.toList())
        return r_list

    def getNames(self, no_kernels, name_changer):
        # TODO no_kernels
        r_list = []
        if self.is_kernel:
            return r_list
        name = self.name if name_changer is None else name_changer(self.name)
        r_list.append(name)
        for child in self.children:
            r_list.extend(child.getNames(no_kernels, name_changer))
        return r_list

    def rollupKernelTime(self):
        kernel_dur = 0
        if self.is_kernel:
            return self.duration
        for child in self.children:
            kernel_dur += child.rollupKernelTime()
        self.kernel_duration = kernel_dur
        self.duration += kernel_dur
        return kernel_dur

    def allKernels(self):
        r_list = []
        if self.is_kernel:
            r_list.append(self)
        for child in self.children:
            r_list.extend(child.allKernels())
        return r_list

    def allCPUOps(self):
        r_list = []
        if not self.is_kernel:
            r_list.append(self)
        for child in self.children:
            r_list.extend(child.allCPUOps())
        return r_list

    ## TODO: Also add similar function to class Graph when this function
    ## becomes more stable
    def allCPUOpKernelPairs(self):
        '''
        Return a list of (CPU Ops, [list of kernels]) pairs
        Notice that the CPU Ops here are the CPU Ops at the lowest level, which means that
        they have at least a direct child being kernel launch
        '''
        r_list = []
        local_list = []
        for child in self.children:
            if not child.is_kernel_launch:
                r_list.extend(child.allCPUOpKernelPairs())
            else:
                if len(child.children) > 0:
                    for c in child.children:
                        if c.is_kernel:
                            local_list.append(c)
                else:
                    print("%s is kernel launch but does not have kernel launched" %(child.name))
                    print("Its parent is %s. The start time is %d, duration is %d" %(self.parent.name, self.start, self.duration))
                    print(self)
        if len(local_list) > 0:
            r_list.append((self, local_list))
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

    def nameSearch(self, name):
        return self.top_node.nameSearch(name)

    def toList(self):
        r_list = []
        r_list.extend(self.top_node.toList())
        return r_list

    def getNames(self, no_kernels=False, name_changer=None):
        r_list = []
        r_list.extend(self.top_node.getNames(no_kernels, name_changer))
        return r_list

    def rollupKernelTime(self):
        # TODO: Make a depth arg for how many levels to roll up
        self.top_node.rollupKernelTime()

    def allKernels(self):
        return self.top_node.allKernels()

    def allCPUOps(self):
        return self.top_node.allCPUOps()
