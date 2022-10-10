import re


def calcAllBW(graph):
    kernels = graph.nameSearch("elementwise_kernel")
    for kernel in kernels:

        # Get Dtypesize
        if "float" in kernel.name:
            dtype_size = 4
        else:
            print(f"Unknown dtype for BW calculation \n name: {kernel.name}")
            raise TypeError("Unknown dtype")

        # Get Op type
        # TODO: Label all of these better/Use constants
        if "CUDAFunctor_add" in kernel.name:
            launcher = kernel.parent.parent
            # Get the size out of the name
            match = re.search(".* sizes = (.*) input_op_ids.*", launcher.name)
            # For add it comes in two identical arrays so only take the first
            # Remoce "[", "]", and " " from the string
            size = re.sub("\[|\]| ", "", match.group(1)).split(",")
            m = int(size[0])
            n = int(size[1])
            data_transfer = (m * n * dtype_size * 3) / 1000000000
            data_transfer_persec = data_transfer / (kernel.duration * 0.000001)
            kernel.traceEvent["BW"] = data_transfer_persec
        # else:
        #    print(f"Not Implemented \n name: {kernel.name}")
