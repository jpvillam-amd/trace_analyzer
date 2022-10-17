import re

# Constants
MICROSECOND_TO_SECOND = 0.000001
TO_GB = 1000000000
TWO_LOAD_ONE_STORE = 3
ONE_LOAD_ONE_STORE = 2


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
        # TODO: Makes sure all our assumtions about the name are there...
        if "CUDAFunctor_add" in kernel.name:
            launcher = kernel.parent.parent
            # Get the size out of the name
            match = re.search(".* sizes = (.*) input_op_ids.*", launcher.name)
            # For add it comes in two identical arrays so only take the first
            # Remoce "[", "]", and " " from the string
            size = re.sub("\[|\]| ", "", match.group(1)).split(",")
            m = int(size[0])
            n = int(size[1])
            data_transfer = (m * n * dtype_size * TWO_LOAD_ONE_STORE) / TO_GB
            data_transfer_persec = data_transfer / (
                kernel.duration * MICROSECOND_TO_SECOND
            )
            kernel.traceEvent["BW"] = data_transfer_persec
        elif "BinaryFunctor" in kernel.name:
            launcher = kernel.parent.parent
            # Get the size out of the name
            match = re.search(".* sizes = (.*) input_op_ids.*", launcher.name)
            # For add it comes in two identical arrays so only take the first
            # Remoce "[", "]", and " " from the string
            size = re.sub("\[|\]| ", "", match.group(1)).split(",")
            if "MulFunctor" in kernel.name:
                m_one = int(size[0])
                n_one = int(size[1])
                m_two = int(size[2])
                n_two = int(size[3])
                data_transfer = (
                    ((m_one * n_one) + (m_two * n_two) + (m_one * n_two)) * dtype_size
                ) / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec
            else:
                # Generic Binary function
                print(
                    "Binary function {kernel.name} not implemented using generic formula."
                )
                m = int(size[0])
                n = int(size[1])
                data_transfer = (m * n * dtype_size * TWO_LOAD_ONE_STORE) / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec
        elif "BUnaryFunctor" in kernel.name:
            launcher = kernel.parent.parent
            # Get the size out of the name
            match = re.search(".* sizes = (.*) input_op_ids.*", launcher.name)
            # For add it comes in two identical arrays so only take the first
            # Remoce "[", "]", and " " from the string
            size = re.sub("\[|\]| ", "", match.group(1)).split(",")
            if "MulFunctor" in kernel.name:
                m = int(size[0])
                n = int(size[1])
                data_transfer = (m * n) * ONE_LOAD_ONE_STORE * dtype_size / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec
            else:
                # Generic Binary function
                print(
                    "BUnary function {kernel.name} not implemented using generic formula."
                )
                m = int(size[0])
                n = int(size[1])
                data_transfer = (m * n * dtype_size * ONE_LOAD_ONE_STORE) / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec

        else:
            print(f"Not Implemented \n name: {kernel.name}")


def shortName(name):
    s_name = name.split()[0].replace(",", "")
    s_name = s_name if s_name != "void" else name
    return s_name


def getMedian(nums):
    nums.sort()
    mid = len(nums) // 2
    return (nums[mid] + nums[~mid]) / 2
