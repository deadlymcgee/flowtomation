#!/usr/bin/python3

import sys
import json
import subprocess
import shlex
from collections import OrderedDict
import time
import datetime
import os
import enum
import utilities

# ------------------------------------------------------------------------------
# part 2
import numbers
import validate_time


supported_data_types = {
    "number": numbers.Number,
    "string": str,
    "dictionary": dict,
    "array": list,
    "boolean": bool,
    "time": datetime.datetime
}


class Direction(enum.Enum):
    INBOUND = "input"
    OUTBOUND = "output"


def verify_service_data_format(
        service,
        services,
        service_data,
        direction,
        logger
):
    """
    -service input will be the output of the preceding service in the flow
    -input will be in the form of a JSON formatted string
    :return:
    """
    # get the data type
    data_type_configuration = services.get(service)\
        .get(direction)
    required_data_type = data_type_configuration.get("type")
    required_data_format = None
    # get the required format, if one exists
    if "format" in data_type_configuration:
        required_data_format = data_type_configuration.get("format")
    # verify a data type is configured and it is supported
    if not required_data_type:
        # TODO: provide feedback?
        logger.warning("service: {0} - does not have an {1} data type configured"
                    .format(service, direction))
    elif required_data_type not in supported_data_types:
        logger.error("service: {0} - unsupported data type!"
                     .format(service, direction))
        return False

    # get the data payload
    # service_data = service_data.decode("utf-8")
    try:
        data = json.loads(service_data.decode("utf-8")).get("data")
    except json.JSONDecodeError as e:
        # TODO: create function to extract required output from 'JSONDecodeError' exception
        logger.error("service: {0} - invalid JSON message provided!")
        return False

    # we now have the service input/output data
    # the data type we have needs to be 'tested' against the configured data type
    if required_data_type != "time":
        result = isinstance(
            data,
            supported_data_types.get(required_data_type)
        )
    else:
        if not required_data_format:
            result = validate_time.convert_datetime_string_part2(data)
        else:
            result = validate_time.convert_datetime_string_part2(data, required_data_format)
    return result


# def get_configuration_part_2(
#         service,
#         service
# ):
#     pass
#
def get_services_part_2(
        services,
        file_information,
        logger
):
    # search recursively for config.json files in 'services' directory
    result = ''
    # services = {}
    get_failed = False
    for root, dirs, files in os.walk("services"):
        for file in files:
            if file == "config.json":
                # check if file information exists or the config has ben modified
                # service name is the parent directory name
                config_file_path = os.path.join(root, file)
                if utilities.check_file_modified(
                    config_file_path,
                    file_information,
                    logger
                ):
                    # load the service
                    # TODO: handle the result (return value 'True' or 'False')
                    service_name = os.path.basename(root)
                    log_line_prefix = "service: {0} -".format(service_name)
                    # verify if valid JSON via 'load_service'
                    if utilities.load_service(
                        services,
                        service_name,
                        config_file_path,
                        logger
                    ):
                        logger.info("{0} loaded successfully!".format(log_line_prefix))

                    else:
                        logger.error("{0} failed to load!".format(log_line_prefix))
                        return False
                    # verify mandatory fields (configuration)
                    if utilities.verify_configuration(
                            services.get(service_name),
                            utilities.required_keys.get("service_configuration"),
                            logger
                    ):
                        logger.info("{0} passed mandatory field verification!".format(log_line_prefix))
                    else:
                        logger.error("{0} failed mandatory field verification".format(log_line_prefix))
                        # remove the service from running configuration
                        del services[service_name]
                        get_failed = True
        continue
    if get_failed:
        return False
    return True

# # ------------------------------------------------------------------------------
#
#
# def get_services_part_1():
#
#     return services


def get_configuration_part_1(
        service,
        services,
        service_output
):
    program = services.get(service)["program"]
    parameters = services.get(service)["parameters"]
    # check for special symbol '$$' in parameters
    if "$$" in parameters:
        parameters = parameters.replace("$$", service_output.decode("utf-8"))
    # part 2 only
    # check if the service uses a custom python script
    path = ''
    if "./" in program:
        program = program[2:]
        path = "%s/%s/" % (
            "services",
            # escape any spaces so shlex doesnt split the directory name
            " ".join(["%s\\" % line for line in service.split()])
        )

    command_line = shlex.split(
                    '%s%s %s' % (
                        path,
                        program,
                        parameters
                    ),
                )
    return command_line


def process_flow(f, flows, services, logger):
    # TODO: docstring
    # store our service output to use as input for the next service
    service_output = ''

    # part 2
    # check if all services listed in the flow loaded successfully
    if not utilities.flow_ready_to_run(
            services,
            flows,
            f,
            logger
    ):
        return False

    for service in flows.get(f):
        # TODO: check for service_output here instead of 'verify_service_data_format'
        # part 2 only
        # verify service input i.e. 'service_output'
        # TODO: handle exception raised by 'verify_service_data_format'
        if service_output and not verify_service_data_format(
            service,
            services,
            service_output,
            Direction.INBOUND.value,
            logger
        ):
            return False

        # handle a possible exception if the service exits with a non-zero exit code
        # TODO: test other possible exceptions:
        # -service file/command not found
        # -permission issue on service file
        try:
            result = subprocess.run(
                get_configuration_part_1(
                    service,
                    services,
                    service_output
                ),
                input=service_output,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            service_output = result.stdout
            if not verify_service_data_format(
                service,
                services,
                service_output,
                Direction.OUTBOUND.value,
                logger
            ):
                return False
        except subprocess.CalledProcessError as e:
            result = e
            pass
        # return error code if stderr
        status = result.returncode

        # exit flow on non-zero return code
        if status != 0:
            return False
        continue
    return True


def main():
    # setup logging
    logger = utilities.setup_logger("CPT223 A2")

    flow_configuration_file = ''
    # get the configuration file from the command line if one supplied
    command_line_argument = sys.argv[1]
    if command_line_argument:
        flow_configuration_file = command_line_argument
    else:
        flow_configuration_file = "ifttt.json"

    # get the program configuration
    # TODO: handle invalid json etc per specs
    # part 1
    # program_configuration_file = "test.json"
    # try:
    #     configuration = json.load(
    #         open(program_configuration_file),
    #         object_pairs_hook=OrderedDict
    #     )
    #     logger.info("configuration loaded!")
    # except json.JSONDecodeError as e:
    #     error_message = "Failed to load configuration - Invalid JSON detected on line: {0}".format(e.lineno - 1)
    #     logger.critical(error_message)
    #     sys.exit(error_message)
    # # get the flow configuration
    # flows = configuration.get("flows")
    # logger.info("got the flows!")

    # get the services
    services = {}
    # part 1
    # services = configuration.get("services")

    # part 2
    file_information = {}

    # process the flows
    while True:
        # TODO: take action if the time taken of previous run is > 60 seconds??

        logger.info("waiting for next flow start time ...")
        if utilities.flow_start_time():
            logger.info("it's go time!")
            # part 2
            # update/check the flow configuration file modified time
            modified = utilities.check_file_modified(
                flow_configuration_file,
                file_information,
                logger
            )
            if modified:
                # load the flow configuration
                try:
                    configuration = json.load(
                        open(flow_configuration_file),
                        object_pairs_hook=OrderedDict
                    )
                    logger.info("configuration loaded!")
                except json.JSONDecodeError as e:
                    error_message = "Failed to load configuration - Invalid JSON detected on line: {0}"\
                        .format(e.lineno - 1)
                    logger.critical(error_message)
                    sys.exit(error_message)

                # verify the mandatory configuration fields
                utilities.verify_configuration(
                    configuration,
                    utilities.required_keys.get("program_configuration_1"),
                    logger
                )
                # get the flow configuration
                flows = configuration.get("flows")
                logger.info("got the flows!")
            # update/check the service configuration files modified time
            # and load any new/updated service configurations
            if get_services_part_2(
                services,
                file_information,
                logger
            ):
                logger.info("got the services!")
            else:
                logger.warning("Error encountered getting services - please review the service configurations")
                # sys.exit("Error encountered loading services - see log file for details")

            logger.info("starting flows")
            for flow, service_list in flows.items():
                logger.info("running flow: {0}".format(flow))
                flow_status = ""
                start_time = datetime.datetime.now()
                # check the status of the flow
                log_line_prefix = "flow: {0} status -".format(flow)
                if process_flow(flow, flows, services, logger):
                    flow_status = "successful!"
                    logger.info("{0} successful!".format(log_line_prefix))
                else:
                    flow_status = "failed!"
                    logger.info("{0} failed!".format(log_line_prefix))
                time_taken = datetime.datetime.now() - start_time
                continue
        # time.sleep(1)

    sys.exit()


if __name__ == "__main__":
    main()












