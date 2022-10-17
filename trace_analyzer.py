import json
from trace_graph import Graph, Node
from trace_utils import calcAllBW, shortName, getMedian
from collections.abc import Iterable
import xlsxwriter
import argparse


def getIterationTimes(data, iteration, num_iterations=1):
    starting_time = 0
    ending_time = float("inf")
    iteration_start = str(iteration)
    iteration_stop = str(iteration + num_iterations)
    for i in range(0, len(data["traceEvents"])):
        try:
            if ("iteration" + iteration_start) in data["traceEvents"][i]["name"]:
                starting_time = int(data["traceEvents"][i]["ts"])
            if ("iteration" + iteration_stop) in data["traceEvents"][i]["name"]:
                ending_time = int(data["traceEvents"][i]["ts"])
            if ("ProfilerStep#" + iteration_start) in data["traceEvents"][i]["name"]:
                starting_time = int(data["traceEvents"][i]["ts"])
            if ("ProfilerStep#" + iteration_stop) in data["traceEvents"][i]["name"]:
                ending_time = int(data["traceEvents"][i]["ts"])
        except KeyError:
            pass
    return starting_time, ending_time


def processJson(file_name, iteration=None):
    f = open(file_name)
    data = json.load(f)
    g = Graph()
    starting_time = 0
    ending_time = float("inf")
    kernels = {}
    op_links = {}

    if iteration is not None:
        starting_time, ending_time = getIterationTimes(data, iteration)

    for i in range(0, len(data["traceEvents"])):
        # TODO: put the time check on its own if
        if (
            (data["traceEvents"][i].keys() >= {"name", "ts", "dur", "args"})
            and (int(data["traceEvents"][i]["ts"]) >= starting_time)
            and (int(data["traceEvents"][i]["ts"]) <= ending_time)
        ):
            n = Node(data["traceEvents"][i])
            if n.is_kernel:
                kernels[n.start] = n
            else:
                # The "hints" from amd side would count twice
                if "UserMarker" not in data["traceEvents"][i]["args"].setdefault(
                    "desc", ""
                ):
                    g.addNode(n)
        # XXX: Sometime kernels are launched after the iteration, choosing an arbritary buffer.
        elif (
            (data["traceEvents"][i].keys() >= {"name", "ts", "dur", "args"})
            and (int(data["traceEvents"][i]["ts"]) >= starting_time)
            and (int(data["traceEvents"][i]["ts"]) <= ending_time + 1000000)
        ):
            n = Node(data["traceEvents"][i])
            if n.is_kernel:
                kernels[n.start] = n
        elif (
            (data["traceEvents"][i].keys() >= {"name", "ts", "cat", "ph"})
            and (data["traceEvents"][i]["ph"] in ("f", "s"))
            and (int(data["traceEvents"][i]["ts"]) >= starting_time)
            and (
                (int(data["traceEvents"][i]["ts"]) <= ending_time)
                or data["traceEvents"][i]["id"] in op_links.keys()
            )
        ):
            op_links.setdefault(data["traceEvents"][i]["id"], []).append(
                data["traceEvents"][i]
            )

    for key in op_links.keys():
        if len(op_links[key]) != 2:
            continue
        # TODO: Once we fix AMD do this on correlation IDs not timestamps
        op_link_start = (
            op_links[key][0] if op_links[key][0]["ph"] == "s" else op_links[key][1]
        )
        op_link_finish = (
            op_links[key][0] if op_links[key][0]["ph"] == "f" else op_links[key][1]
        )
        kernel = kernels[int(op_link_finish["ts"])]
        launcher = g.search(int(op_link_start["ts"]))
        # XXX: breaking time guarantee of graph
        launcher.children.append(kernel)
        kernel.parent = launcher

    return g


def summarizeResults(g):
    all_ops = {}
    for node in g.toList():
        name = shortName(node.name)
        op_total, op_max, op_min, ops, op_count = all_ops.setdefault(
            name, [0, -1, 10000000, [], 0]
        )
        op_dur = node.duration
        op_total += op_dur
        op_max = op_max if op_max > op_dur else op_dur
        op_min = op_min if op_min < op_dur else op_dur
        op_count += 1
        ops.append(op_dur)
        all_ops[name] = [op_total, op_max, op_min, ops, op_count]
    return all_ops


def printTableSumary(name_one, name_two, all_ops_one, all_ops_two, ops_to_print):
    # TODO: print unshared OPs
    print(
        f"{'':50} {name_one:7.6}{'max':5}{'min':5}{'median':8}{'count':7}"
        f"{name_two:7.6}{'max':5}{'min':5}{'median':8}{'count':7}{'Rdiff':7}"
    )
    for key in ops_to_print:
        if key == "top_node":
            continue
        median_one = getMedian(all_ops_one[key][3])
        median_two = getMedian(all_ops_two[key][3])

        print(
            f"{key:48.45}{all_ops_one[key][0]:6}{all_ops_one[key][1]:7}"
            f"{all_ops_one[key][2]:5}{median_one:8}{all_ops_one[key][4]:7}"
            f"{all_ops_two[key][0]:8}{all_ops_two[key][1]:4}{all_ops_two[key][2]:5}"
            f"{median_two:8}{all_ops_two[key][4]:7}"
            f"{all_ops_two[key][0]/all_ops_one[key][0]:7.3}"
        )


# TODO: pass formats more elegantly
def writeSingleSummary(
    name, workbook, keys, results, bold_format, rotate_format, redge_format
):
    worksheet = workbook.add_worksheet(f"{name}_only_Ops")
    headers = ["Operation", name, "max(ms)", "min(ms)", "median(ms)", "count"]
    # Write header
    h = 0
    for header in headers:
        worksheet.write(
            0, h, header, bold_format if header in ("Operation") else rotate_format
        )
        h += 1
    r = 1
    for op in keys:
        worksheet.write(r, 0, op, redge_format)
        result = results[op]
        for c in range(len(result)):
            value = (
                result[c] if not isinstance(result[c], Iterable) else getMedian(result[c])
            )
            worksheet.write(r, c + 1, value)
        r += 1

    # Formating
    worksheet.set_column(0, 0, 45)
    worksheet.set_column(1, 5, 6)
    worksheet.conditional_format(1, 1, r, 1, {"type": "data_bar", "bar_color": "#FF555A"})


def getAllVariations(graph, keys):
    g_as_list = graph.toList()
    variation_dict = {}
    for key in keys:
        variations = {}
        for node in g_as_list:
            if shortName(node.name) == key:
                # Dumb hash of just name child names together
                variation_hash = key
                for child in node.children:
                    # Remove non-alphanumberic characters.
                    # Bypass the kernellaunch ops
                    if child.is_kernel_launch and len(child.children) == 1:
                        s_name = shortName(child.children[0].name)
                    else:
                        s_name = shortName(child.name)
                    variation_hash += "".join(c for c in s_name if c.isalnum())
                reference, count, total_duration = variations.setdefault(
                    variation_hash, [None, 0, 0]
                )
                if reference is None:
                    reference = node
                count += 1
                total_duration += node.duration
                variations[variation_hash] = [reference, count, total_duration]
        variation_dict[key] = variations
    return variation_dict


def writeAllVariatons(variations, workbook, name, map_sheet, map_column):
    sheet_num = 0
    worksheet_map = {}
    for key in variations:
        # if len(variations[key].keys()) < 2:
        #   # Just one variation, skip.
        #   continue

        key_clean = "".join(c for c in key if c.isalnum())
        worksheet_name = f"{sheet_num}_{name}_{key_clean}"
        sheet_num += 1
        worksheet = workbook.add_worksheet(worksheet_name[:28])
        worksheet_map[key] = worksheet_name[:28]
        worksheet.set_column(0, 15, 35)

        r = 0
        for variation_hash in variations[key].keys():
            c = 0
            node = variations[key][variation_hash][0]
            count = variations[key][variation_hash][1]
            duration = variations[key][variation_hash][2]
            worksheet.write(r, c, node.name)
            worksheet.write(r, c + 1, f"Count: {count}")
            worksheet.write(r, c + 2, f"Duration: {duration}")
            c += 1
            r += 1
            for child in node.children:
                # Skip launch layer
                if child.is_kernel_launch and len(child.children) == 1:
                    child_resolved = child.children[0]
                else:
                    child_resolved = child
                c_name = child_resolved.name
                c_duration = child_resolved.duration
                worksheet.write(r, c, c_name)
                worksheet.write(r, c + 1, f"Duration: {c_duration}")
                if "BW" in child_resolved.traceEvent.keys():
                    bw = child_resolved.traceEvent["BW"]
                    worksheet.write(r, c + 2, f"BW efficiency: {bw}")
                r += 1
            r += 6

        worksheet.write_url(r, 0, f"internal:{map_sheet.get_name()}!A1", string="Index")

    r = 0
    for key in worksheet_map.keys():
        map_sheet.write_url(
            r,
            map_column,
            f"internal:{worksheet_map[key]}!A1",
            string=f"{worksheet_map[key]}",
        )
        r += 1


def writeBandwidthSheet(g, name, workbook, bold_format):
    worksheet = workbook.add_worksheet(f"{name}_BW")
    headers = ["Kernel", "GB/s"]

    kernels = g.nameSearch("elementwise_kernel")

    # Write header
    h = 0
    for header in headers:
        worksheet.write(0, h, header, bold_format)
        h += 1
    r = 1
    for kernel in kernels:
        c = 0
        worksheet.write(r, c, kernel.name)
        value = kernel.traceEvent["BW"] if "BW" in kernel.traceEvent.keys() else " "
        worksheet.write(r, c + 1, value)
        r += 1

    # Formating
    worksheet.set_column(0, 0, 45)
    worksheet.set_column(1, 1, 6)


def summarizeResultsKernelBreakdown(graph):
    ops = graph.toList()
    el_kernels = 0
    math_kernels = 0
    other_kernels = 0
    cpu_ops = 0

    for op in ops:
        if op.is_kernel:
            if op.name.startswith("ampere") or op.name.startswith("Cijk"):
                math_kernels += op.duration
            elif "elementwise" in op.name:
                el_kernels += op.duration
            else:
                other_kernels += op.duration
        else:
            cpu_ops += op.duration
    return el_kernels, math_kernels, other_kernels, cpu_ops


def writeKernelBreakdowns(
    times_one, times_two, workbook, name_one, name_two, bold_format
):
    worksheet = workbook.add_worksheet(f"Op_times")
    # Headers
    headers = [name_one, name_two]
    row_headers = ["Elementewise Kernels", "Blas Kernels", "Other Kernels", "CPU Ops"]

    # Write header
    h = 1
    for header in headers:
        worksheet.write(0, h, header, bold_format)
        h += 1

    # Write basic info
    r = 1
    for i in range(len(row_headers)):
        worksheet.write(r, 0, row_headers[i], bold_format)
        worksheet.write(r, 1, times_one[i])
        worksheet.write(r, 2, times_two[i])
        r += 1


def writeXLSX(name_one, name_two, g_one, g_two, args):
    workbook = xlsxwriter.Workbook(f"report_{name_one}_{name_two}.xlsx")
    worksheet_comparison = workbook.add_worksheet("Comparison")

    # Formats
    bold_format = workbook.add_format(
        {"bold": True, "border_color": "black", "bottom": 5}
    )
    redge_format = workbook.add_format({"border_color": "black", "right": 5})
    ledge_format = workbook.add_format({"border_color": "black", "left": 5})
    rotate_format = workbook.add_format(
        {"rotation": 45, "border_color": "black", "border": 1, "bottom": 5}
    )

    headers = [
        "Operation",
        name_one,
        "max(ms)",
        "min(ms)",
        "median(ms)",
        "count",
        name_two,
        "max(ms)",
        "min(ms)",
        "median(ms)",
        "count",
        "Diff Total",
        "Diff Median",
        "Diff ratio",
    ]

    # Process data
    summarized_ops_one = summarizeResults(g_one)
    summarized_ops_two = summarizeResults(g_two)

    shared_ops = set(summarized_ops_one.keys()).intersection(
        set(summarized_ops_two.keys())
    )
    shared_ops.remove("top_node")

    # Set columns width
    worksheet_comparison.set_column(0, 0, 45)
    worksheet_comparison.set_column(1, 10, 4)

    # Write header
    h = 0
    for header in headers:
        worksheet_comparison.write(
            0, h, header, bold_format if header in ("Operation") else rotate_format
        )
        h += 1

    # Write basic info
    r = 1
    for op in shared_ops:
        op_summary = summarized_ops_one[op] + summarized_ops_two[op]
        worksheet_comparison.write(r, 0, op, redge_format)
        for c in range(len(op_summary)):
            value = (
                op_summary[c]
                if not isinstance(op_summary[c], Iterable)
                else getMedian(op_summary[c])
            )
            worksheet_comparison.write(r, c + 1, value)
        r += 1

    # Write comparison info
    r = 1
    for op in shared_ops:
        c = (len(summarized_ops_one[op]) * 2) + 1
        diff_total = summarized_ops_one[op][0] - summarized_ops_two[op][0]
        diff_median = getMedian(summarized_ops_one[op][3]) - getMedian(
            summarized_ops_two[op][3]
        )
        diff_ratio = summarized_ops_two[op][0] / summarized_ops_one[op][0]
        worksheet_comparison.write(r, c, diff_total, ledge_format)
        worksheet_comparison.write(r, c + 1, diff_median)
        worksheet_comparison.write(r, c + 2, diff_ratio)
        r += 1

    # Conditional Formating
    c = (len(summarized_ops_one[op]) * 2) + 1
    worksheet_comparison.conditional_format(
        1, c, r, c + 1, {"type": "data_bar", "bar_color": "#FF555A"}
    )
    worksheet_comparison.conditional_format(
        1,
        c + 2,
        r,
        c + 2,
        {
            "type": "3_color_scale",
            "max_color": "#63BE7B",
            "min_color": "#F8696B",
            "mid_color": "#FFEB84",
            "mid_type": "percent",
        },
    )

    # Write Non-shared Ops
    # TODO: Use sets to make the keys?
    summarized_ops_one_only = [
        x for x in summarized_ops_one.keys() if x not in summarized_ops_two.keys()
    ]
    writeSingleSummary(
        name_one,
        workbook,
        summarized_ops_one_only,
        summarized_ops_one,
        bold_format,
        rotate_format,
        redge_format,
    )
    summarized_ops_two_only = [
        x for x in summarized_ops_two.keys() if x not in summarized_ops_one.keys()
    ]
    writeSingleSummary(
        name_two,
        workbook,
        summarized_ops_two_only,
        summarized_ops_two,
        bold_format,
        rotate_format,
        redge_format,
    )

    # Write Elementwise BW if enabled.
    if args.calculate_elementwise_eff:
        writeBandwidthSheet(g_one, name_one, workbook, bold_format)
    # Get and write kernel summary:
    if args.kernel_stats:
        times_one = summarizeResultsKernelBreakdown(g_one)
        times_two = summarizeResultsKernelBreakdown(g_two)
        writeKernelBreakdowns(
            times_one, times_two, workbook, name_one, name_two, bold_format
        )
    # Variation Map
    if args.variations:
        worksheet_variation = workbook.add_worksheet(f"Variation_Map")
        var = getAllVariations(g_one, g_one.getNames(True, shortName))
        writeAllVariatons(var, workbook, name_one, worksheet_variation, 0)
        var = getAllVariations(g_two, g_two.getNames(True, shortName))
        writeAllVariatons(var, workbook, name_two, worksheet_variation, 1)
        worksheet_variation.set_column(0, 1, 45)

    workbook.close()


def main():
    parser = argparse.ArgumentParser(description="Comparison script for trace files.")
    parser.add_argument(
        "-f",
        "--first",
        nargs=3,
        help="Name, Iteration number, and file for the first trace to compare",
        required=True,
    )
    parser.add_argument(
        "-s",
        "--second",
        nargs=3,
        help="Name, Iteration number, and file for the second trace to compare",
        required=True,
    )
    parser.add_argument(
        "--variations",
        action="store_true",
        default=False,
        help="Creates and view of the tree and shows all variations of ops called.",
    )
    parser.add_argument(
        "--blocking", action="store_true", help="Forces blocking like behavior"
    )
    parser.add_argument("--no-blocking", dest="blocking", action="store_false")
    parser.set_defaults(blocking=False)
    parser.add_argument(
        "--calculate-elementwise-eff",
        action="store_true",
        default=False,
        help="Calculated BW efficiency for elemenwise kernels. "
        "Requires shapes and assume databound kernels.",
    )
    parser.add_argument(
        "--kernel-stats",
        action="store_true",
        default=False,
        help="Creates a summary sheet of aggregated kernel times and cpu time.",
    )
    args = parser.parse_args()

    iteration_one = int(args.first[1]) if args.first[1] != "None" else None
    iteration_two = int(args.second[1]) if args.first[1] != "None" else None

    g_one = processJson(args.first[2], iteration_one)
    g_two = processJson(args.second[2], iteration_two)

    if args.blocking:
        # Roll up all kernel times back to their caller chains
        g_one.rollupKernelTime()
        g_two.rollupKernelTime()

    if args.calculate_elementwise_eff:
        # Calculates BW efficiency for some kernels.
        calcAllBW(g_one)

    if False:
        # TODO: Print to command line more efficently
        all_ops_one = summarizeResults(g_one)
        all_ops_two = summarizeResults(g_two)

        shared_ops = set(all_ops_one.keys()).intersection(set(all_ops_two.keys()))
        divergent_ops = set(all_ops_one.keys()).symmetric_difference(
            set(all_ops_two.keys())
        )
        printTableSumary(
            args.first[0], args.second[0], all_ops_one, all_ops_two, shared_ops
        )

    writeXLSX(args.first[0], args.second[0], g_one, g_two, args)


if __name__ == "__main__":
    main()
