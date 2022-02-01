// Copyright (c) 2016 The Zcash developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or https://www.opensource.org/licenses/mit-license.php .

#include "asyncrpcoperation.h"
#include "util.h"

#include <boost/uuid/uuid.hpp>
#include <boost/uuid/uuid_generators.hpp>
#include <boost/uuid/uuid_io.hpp>

#include <string>
#include <ctime>
#include <chrono>

#include <unistd.h>
#include <sys/syscall.h>
#include <linux/perf_event.h>

using namespace std;

static boost::uuids::random_generator uuidgen;

static std::map<OperationStatus, std::string> OperationStatusMap = {
    {OperationStatus::READY, "queued"},
    {OperationStatus::EXECUTING, "executing"},
    {OperationStatus::CANCELLED, "cancelled"},
    {OperationStatus::FAILED, "failed"},
    {OperationStatus::SUCCESS, "success"}
};

/**
 * Every operation instance should have a globally unique id
 */
AsyncRPCOperation::AsyncRPCOperation() : error_code_(0), error_message_() {
    // Set a unique reference for each operation
    boost::uuids::uuid uuid = uuidgen();
    id_ = "opid-" + boost::uuids::to_string(uuid);
    creation_time_ = (int64_t)time(NULL);
    set_state(OperationStatus::READY);
}

AsyncRPCOperation::AsyncRPCOperation(const AsyncRPCOperation& o) :
        id_(o.id_), creation_time_(o.creation_time_), state_(o.state_.load()),
        start_time_(o.start_time_), end_time_(o.end_time_),
        error_code_(o.error_code_), error_message_(o.error_message_),
        result_(o.result_)
{
}

AsyncRPCOperation& AsyncRPCOperation::operator=( const AsyncRPCOperation& other ) {
    this->id_ = other.id_;
    this->creation_time_ = other.creation_time_;
    this->state_.store(other.state_.load());
    this->start_time_ = other.start_time_;
    this->end_time_ = other.end_time_;
    this->error_code_ = other.error_code_;
    this->error_message_ = other.error_message_;
    this->result_ = other.result_;
    return *this;
}


AsyncRPCOperation::~AsyncRPCOperation() {
}

/**
 * Override this cancel() method if you can interrupt main() when executing.
 */
void AsyncRPCOperation::cancel() {
    if (isReady()) {
        set_state(OperationStatus::CANCELLED);
    }
}

/**
 * Start timing the execution run of the code you're interested in
 */
void AsyncRPCOperation::start_execution_clock() {
    std::lock_guard<std::mutex> guard(lock_);
    start_time_ = std::chrono::system_clock::now();

    struct perf_event_attr attr;
    attr.type = PERF_TYPE_SOFTWARE;
    attr.config = PERF_COUNT_SW_CPU_CLOCK;
    attr.size = PERF_ATTR_SIZE_VER6;
    attr.inherit = 1;
    attr.disabled = 0;
    attr.sample_period=0;
    attr.sample_type=0;
    attr.read_format=0;

    attr.pinned=0;
    attr.exclusive=0;
    attr.exclude_kernel=0;
    attr.exclude_hv=0;
    attr.exclude_idle=0;
    attr.mmap=0;
    attr.comm=0;
    attr.freq=0;
    attr.inherit_stat=0;
    attr.enable_on_exec=0;
    attr.task=0;
    attr.watermark=0;
    attr.precise_ip=0 /* arbitrary skid */;
    attr.mmap_data=0;
    attr.sample_id_all=0;
    attr.exclude_host=0;
    attr.exclude_guest=0;
    attr.exclude_callchain_kernel=0;
    attr.exclude_callchain_user=0;
    attr.mmap2=0;
    attr.comm_exec=0;
    attr.use_clockid=0;
    attr.context_switch=0;
    attr.write_backward=0;
    attr.namespaces=0;
    attr.wakeup_events=0;
    attr.config1=0;
    attr.config2=0;
    attr.sample_regs_user=0;
    attr.sample_regs_intr=0;
    attr.aux_watermark=0;
    attr.sample_max_stack=0;
    attr.aux_sample_size=0;


    perf_event_fd = syscall(__NR_perf_event_open, &attr, 0, -1, -1, 0);
    LogPrintf("time units, GOT AN FD %d!\n\n\n", perf_event_fd);
     if (perf_event_fd == -1 || read(perf_event_fd, &time_units_start, sizeof(time_units_start)) < (ssize_t)sizeof(time_units_start)) {
        time_units_start = 42069;
    }
    if (perf_event_fd == -1){
        LogPrintf("time units, got errno", strerror(errno));   
    }
    LogPrintf("time units start is: %lld\n", time_units_start);


}

/**
 * Stop timing the execution run
 */
void AsyncRPCOperation::stop_execution_clock() {
    std::lock_guard<std::mutex> guard(lock_);
    end_time_ = std::chrono::system_clock::now();
    LogPrintf("time units USING USINNGGGGG USING AN FD %d!\n\n\n", perf_event_fd);

    if (perf_event_fd == -1 || read(perf_event_fd, &time_units_finish, sizeof(time_units_finish)) < (ssize_t)sizeof(time_units_finish)) {
        time_units_finish = 42069;
    }
    LogPrintf("time units end is: %lld\n", time_units_finish);

    LogPrintf("Used %lld time units whatever they are\n", time_units_finish-time_units_start);

}

/**
 * Implement this virtual method in any subclass.  This is just an example implementation.
 */
void AsyncRPCOperation::main() {
    if (isCancelled()) {
        return;
    }
    
    set_state(OperationStatus::EXECUTING);

    start_execution_clock();

    // Do some work here..

    stop_execution_clock();

    // If there was an error, you might set it like this:
    /*
    setErrorCode(123);
    setErrorMessage("Murphy's law");
    setState(OperationStatus::FAILED);
    */

    // Otherwise, if the operation was a success:
    UniValue v(UniValue::VSTR, "We have a result!");
    set_result(v);
    set_state(OperationStatus::SUCCESS);
}

/**
 * Return the error of the completed operation as a UniValue object.
 * If there is no error, return null UniValue.
 */
UniValue AsyncRPCOperation::getError() const {
    if (!isFailed()) {
        return NullUniValue;
    }

    std::lock_guard<std::mutex> guard(lock_);
    UniValue error(UniValue::VOBJ);
    error.pushKV("code", this->error_code_);
    error.pushKV("message", this->error_message_);
    return error;
}

/**
 * Return the result of the completed operation as a UniValue object.
 * If the operation did not succeed, return null UniValue.
 */
UniValue AsyncRPCOperation::getResult() const {
    if (!isSuccess()) {
        return NullUniValue;
    }

    std::lock_guard<std::mutex> guard(lock_);
    return this->result_;
}


/**
 * Returns a status UniValue object.
 * If the operation has failed, it will include an error object.
 * If the operation has succeeded, it will include the result value.
 * If the operation was cancelled, there will be no error object or result value.
 */
UniValue AsyncRPCOperation::getStatus() const {
    OperationStatus status = this->getState();
    UniValue obj(UniValue::VOBJ);
    obj.pushKV("id", this->id_);
    obj.pushKV("status", OperationStatusMap[status]);
    obj.pushKV("creation_time", this->creation_time_);
    // TODO: Issue #1354: There may be other useful metadata to return to the user.
    UniValue err = this->getError();
    if (!err.isNull()) {
        obj.pushKV("error", err.get_obj());
    }
    UniValue result = this->getResult();
    if (!result.isNull()) {
        obj.pushKV("result", result);

        // Include execution time for successful operation
        std::chrono::duration<double> elapsed_seconds = end_time_ - start_time_;
        obj.pushKV("execution_secs", elapsed_seconds.count());
        obj.pushKV("time_units_burnt", time_units_finish-time_units_start);

    }
    return obj;
}

/**
 * Return the operation state in human readable form.
 */
std::string AsyncRPCOperation::getStateAsString() const {
    OperationStatus status = this->getState();
    return OperationStatusMap[status];
}
