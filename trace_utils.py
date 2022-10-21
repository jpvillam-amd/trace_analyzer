import re
import json

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
        elif "BFloat16" in kernel.name:
            dtype_size = 2
        else:
            print(f"Unknown dtype for BW calculation \n name: {kernel.name}")
            raise TypeError("Unknown dtype")

        # Get op that started the kernel
        launcher = kernel.parent.parent

        # Get size of the inputs
        if ("args" in launcher.traceEvent) and (
            "Input Dims" in launcher.traceEvent["args"]
        ):
            sizes = launcher.traceEvent["args"]["Input Dims"]
        else:
            # RPD... Get the size out of the name
            # TODO: Makes sure all our assumtions about the name are there...

            match = re.search(".* sizes = (.*), input_op_ids.*", launcher.name)
            sizes = json.loads(match.group(1))
            launcher.traceEvent["args"]["Input Dims"] = sizes

        # Get Op type
        if "CUDAFunctor_add" in kernel.name:
            dims_multiplied = 1
            for n in sizes[0]:
                dims_multiplied *= n
            data_transfer = (dims_multiplied * dtype_size * TWO_LOAD_ONE_STORE) / TO_GB
            data_transfer_persec = data_transfer / (
                kernel.duration * MICROSECOND_TO_SECOND
            )
            kernel.traceEvent["BW"] = data_transfer_persec
        elif "BinaryFunctor" in kernel.name:
            if "MulFunctor" in kernel.name:
                # TODO: Support N dimentional MulFunctors
                if len(sizes[0]) > 2:
                    print(f"Unsupported {len(sizes[0])}-dimentional MulFunctor")
                    continue

                m_one = sizes[0][0]
                n_one = sizes[0][1]
                m_two = sizes[1][0]
                n_two = sizes[1][1]
                data_transfer = (
                    ((m_one * n_one) + (m_two * n_two) + (m_one * n_two)) * dtype_size
                ) / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec
            else:
                # Generic Binary function
                # print(
                # "Binary function {kernel.name} not implemented using generic formula."
                # )
                dims_multiplied = 1
                for n in sizes[0]:
                    dims_multiplied *= n
                data_transfer = (
                    dims_multiplied * dtype_size * TWO_LOAD_ONE_STORE
                ) / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec
        elif "BUnaryFunctor" in kernel.name:
            if "MulFunctor" in kernel.name:
                # TODO: Support N dimentional MulFunctors
                if len(sizes[0]) > 2:
                    print(f"Unsupported {len(sizes[0])}-dimentional MulFunctor")
                    continue
                m = sizes[0][0]
                n = sizes[0][1]
                data_transfer = (m * n) * ONE_LOAD_ONE_STORE * dtype_size / TO_GB
                data_transfer_persec = data_transfer / (
                    kernel.duration * MICROSECOND_TO_SECOND
                )
                kernel.traceEvent["BW"] = data_transfer_persec
            else:
                dims_multiplied = 1
                for n in sizes[0]:
                    dims_multiplied *= n
                data_transfer = (
                    dims_multiplied * dtype_size * ONE_LOAD_ONE_STORE
                ) / TO_GB
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
