#! /usr/bin/env python

import time
import simplejson as json

# The Job class
class Job(object):
    def __init__(self, client, id, data, priority, tags, worker, expires, state, queue, remaining, retries, failure={}, history=[]):
        # The redis instance this job is associated with
        self.client    = client
        # The actual meat and potatoes of the job
        self.id        = id
        self.data      = data or {}
        self.priority  = priority
        self.tags      = tags or []
        self.worker    = worker
        self.expires   = expires
        self.state     = state
        self.queue     = queue
        self.retries   = retries
        self.remaining = remaining
        self.failure   = failure or {}
        self.history   = history or []
    
    def __getitem__(self, key):
        return self.data.get(key)
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def __str__(self):
        import pprint
        s  = 'qless:Job : %s\n' % self.id
        s += '\tpriority: %i\n' % self.priority
        s += '\ttags: %s\n' % ', '.join(self.tags)
        s += '\tworker: %s\n' % self.worker
        s += '\texpires: %i\n' % self.expires
        s += '\tstate: %s\n' % self.state
        s += '\tqueue: %s\n' % self.queue
        s += '\thistory:\n'
        for h in self.history:
            s += '\t\t%s (%s)\n' % (h['queue'], h['worker'])
            s += '\t\tput: %i\n' % h['put']
            if h['popped']:
                s += '\t\tpopped: %i\n' % h['popped']
            if h['completed']:
                s += '\t\tcompleted: %i\n' % h['completed']
        s += '\tdata: %s' % pprint.pformat(self.data)
        return s
    
    def __repr__(self):
        return '<qless:Job %s>' % self.id
    
    def ttl(self):
        '''How long until this expires, in seconds'''
        return time.time() - self.expires
    
    def move(self, queue):
        '''Put(1, queue, id, data, now, [priority, [tags, [delay]]])
        ---------------------------------------------------------------    
        Either create a new job in the provided queue with the provided attributes,
        or move that job into that queue. If the job is being serviced by a worker,
        subsequent attempts by that worker to either `heartbeat` or `complete` the
        job should fail and return `false`.
        
        The `priority` argument should be negative to be run sooner rather than 
        later, and positive if it's less important. The `tags` argument should be
        a JSON array of the tags associated with the instance and the `valid after`
        argument should be in how many seconds the instance should be considered 
        actionable.'''
        return self.client._put([queue], [
            self.id,
            json.dumps(self.data),
            time.time()
        ])
    
    def complete(self, next=None, delay=None):
        '''Complete(0, id, worker, queue, now, [data, [next, [delay]]])
        -----------------------------------------------
        Complete a job and optionally put it in another queue, either scheduled or to
        be considered waiting immediately.'''
        if next:
            return self.client._complete([], [self.id, self.client.worker, self.queue,
                time.time(), json.dumps(self.data), next, delay or 0]) or False
        else:
            return self.client._complete([], [self.id, self.client.worker, self.queue,
                time.time(), json.dumps(self.data)]) or False
    
    def heartbeat(self):
        '''Heartbeat(0, id, worker, expiration, [data])
        -------------------------------------------
        Renew the heartbeat, if possible, and optionally update the job's user data.'''
        return float(self.client._heartbeat([], [self.id, self.client.worker, time.time(), json.dumps(self.data)]) or 0)
    
    def fail(self, t, message):
        '''Fail(0, id, worker, type, message, now, [data])
        -----------------------------------------------
        Mark the particular job as failed, with the provided type, and a more specific
        message. By `type`, we mean some phrase that might be one of several categorical
        modes of failure. The `message` is something more job-specific, like perhaps
        a traceback.
        
        This method should __not__ be used to note that a job has been dropped or has 
        failed in a transient way. This method __should__ be used to note that a job has
        something really wrong with it that must be remedied.
        
        The motivation behind the `type` is so that similar errors can be grouped together.
        Optionally, updated data can be provided for the job. A job in any state can be
        marked as failed. If it has been given to a worker as a job, then its subsequent
        requests to heartbeat or complete that job will fail. Failed jobs are kept until
        they are canceled or completed. __Returns__ the id of the failed job if successful,
        or `False` on failure.'''
        return self.client._fail([], [self.id, self.client.worker, t, message, time.time(), json.dumps(self.data)]) or False
    
    def cancel(self):
        '''Cancel(0, id)
        -------------
        Cancel a job from taking place. It will be deleted from the system, and any
        attempts to renew a heartbeat will fail, and any attempts to complete it
        will fail. If you try to get the data on the object, you will get nothing.'''
        return self.client._cancel([], [self.id])
    
    def track(self, *tags):
        args = ['track', self.id, time.time()]
        args.extend(tags)
        return self.client._track([], args)
    
    def untrack(self):
        return self.client._track([], ['untrack', self.id, time.time()])
