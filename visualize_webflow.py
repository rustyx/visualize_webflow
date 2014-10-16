#
#    visualize_webflow.py
#    Copyright (C) 2014  Rustam Abdullaev
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
import string, struct, os, re, sys, glob, argparse, subprocess
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('-d', '--dot', dest='dot', action='store_true', help='invoke DOT to generate a PDF for each flow (requires -o or -s)')
parser.add_argument('-s', '--split', dest='split', action='store_true', help='split output by subflow')
parser.add_argument('--skip-flows', dest='skipFlows', default='', help='comma-separated list of subflows to skip')
parser.add_argument('--skip-states', dest='skipStates', default='', help='comma-separated list of states to skip')
parser.add_argument('--split-states', dest='splitStates', default='', help='comma-separated list of states to split (for frequently used states)')
parser.add_argument('--merge-states-min-inputs', dest='mergeMinTotal', type=int, default=5, help='auto-merge states with at least this many inputs (default 5)')
parser.add_argument('--merge-states-min-common-inputs', dest='mergeMinCommon', type=int, default=3, help='auto-merge states with at least this many common inputs (default 3)')
parser.add_argument('--merge-states-max-diff-inputs', dest='mergeMaxDiff', type=int, default=7, help='auto-merge states with at most this many different inputs (default 7)')
parser.add_argument('--hide-conditions', dest='hideConditions', action='store_true', help='hide decision state conditions')
parser.add_argument('--flow-id-path-steps', dest='flow_id_path_steps', type=int, default=1, help='how many steps in the flow.xml path to use as flow ID (default 1)')
parser.add_argument('-o', '--output', dest='output', default='', help='output DOT file name (ignored if -s is specified)')
parser.add_argument('-v', '--verbose', dest='verbose', action='count', help='be verbose')
parser.add_argument('input', help='the path to <webflow-servlet.xml> or <flow.xml>')
args = parser.parse_args()

ns = {'flowcfg':'http://www.springframework.org/schema/webflow-config', 'beans':'http://www.springframework.org/schema/beans', 'flow':'http://www.springframework.org/schema/webflow'}
skipFlows = set(string.split(args.skipFlows,','))
skipStates = set(string.split(args.skipStates,','))
mergeMinTotal = args.mergeMinTotal
mergeMinCommon = args.mergeMinCommon
mergeMaxDiff = args.mergeMaxDiff
splitStates = set(string.split(args.splitStates,','))
skipTransitions = {}
hideConditions = args.hideConditions

def label(t):
    if not t: return '""'
    return '"' + t.replace('\\', '\\\\').replace('"', '\\"') + '"'
    
def strip_ns(t):
    m = re.match(r'{.*}(.*)',t)
    if m != None:
        return m.group(1)
    return t
    
def process_transition(id, on, prefix, to, trflags):
    global out, nodes, dynCounter
    print '#%s on=%s to=%s' % (id,on,to)
    if on in skipTransitions or to in skipStates:
        return
    if '${' in to:
        m = re.search(r'\${.+}', to)
        to = to + str(dynCounter)
        dynCounter += 1
        nodes[prefix + to] = {'type':'?', 'pos':len(nodes), 'label':m.group(0), 'flags':'', 'refs':[]}
    elif prefix + to not in nodes: # and to == to0:
        nodes[prefix + to] = {'type':'?', 'pos':len(nodes), 'label':to, 'flags':' color="red"', 'refs':[], 'missing':1}
    nodes[id]['refs'].append({'label':on, 'to':prefix + to, 'flags':trflags})

def process_state(prefix, t, flags=''):
    global out, nodes
    if t.get('id') in skipStates:
        return
    id = prefix + t.get('id')
    trflags = ""
    nodes[id] = {'type':strip_ns(t.tag), 'pos':len(nodes), 'label':t.get('id'), 'flags':flags, 'refs':[]}
    for tr in t.findall('flow:transition',ns):
        if tr.get('to'):
            process_transition(id, tr.get('on'), prefix, tr.get('to'), trflags)
        for ex in tr.findall('flow:evaluate',ns):
            if ex.get('result'):
                process_transition(id, tr.get('on'), prefix, '${%s}' % ex.get('result'), trflags)
        for ex in tr.findall('flow:render',ns):
            if ex.get('fragments'):
                nodes[prefix + ex.get('fragments')] = {'type':'fragment', 'pos':len(nodes), 'label':ex.get('fragments'), 'flags':' shape="box" style="dashed,filled" fillcolor="lightgrey"', 'refs':[]}
                process_transition(id, tr.get('on'), prefix, ex.get('fragments'), trflags)
    for tr in t.findall('flow:if',ns):
        cond = tr.get('test')
        if hideConditions: cond = ""
        if len(cond) > 50: cond = cond[0:48] + "..."
        process_transition(id, cond, prefix, tr.get('then'), trflags)
        if tr.get('else'):
            process_transition(id, 'no' if hideConditions else 'not ' + cond, prefix, tr.get('else'), trflags)
    subflow = t.get('subflow')
    if subflow and subflow not in skipFlows:
        nodes[subflow]={'type':'flow', 'pos':len(nodes), 'label':subflow, 'flags':' style="filled" fillcolor="lightblue" color="blue"', 'refs':[], 'external':1}
        nodes[id]['refs'].append({'label':subflow, 'to':subflow, 'flags':' color="blue"', 'external':1})

def merge_nodes(nodes, prefix):
    # build a cross-reference
    for id,node in nodes.items():
        node['to'] = set()
        node['from'] = set()
    for id,node in nodes.items():
        for ref in node['refs']:
            to = ref['to']
            if to in nodes and id != to:
                node['to'] |= {to}
                nodes[to]['from'] |= {id}
    # merge nodes
    for id,node in nodes.items():
        if len(node['to']) < 2:
            continue
        frommap = {}
        for t in node['to']:
            if len(nodes[t]['to']) >= mergeMinTotal:
                #print "%s: %i" % (t, len(nodes[t]['to']))
                ids = ','.join(nodes[t]['from'])
                if ids not in frommap:
                    frommap[ids]=[]
                frommap[ids].append(t)
        if len(frommap) > 1:
            for ids,list1 in frommap.items():
                if len(list1) > 1:
                    # print "# %s: (from=%s) list1=%s" % (id, ids, list1)
                    tomerge = set()
                    for j in range(0,len(list1)-1):
                        if len(tomerge): break
                        to1 = nodes[list1[j]]['to']
                        for i in range(j+1,len(list1)):
                            to2 = nodes[list1[i]]['to']
                            intr = to1.intersection(to2)
                            diff = to1.difference(to2)
                            if len(intr) >= mergeMinCommon and len(diff) <= mergeMaxDiff:
                                # print '# %d/%d: %s <-> %s: %s common=%d different=%d' % (j,i,list1[j],list1[i],to1,len(intr), len(diff))
                                tomerge |= {list1[i], list1[j]}
                    # merge
                    if len(tomerge):
                        if args.verbose:
                            print "# merging: %s" % tomerge
                        tomerge = list(tomerge)
                        merged = tomerge[0]
                        nodes[merged]['label'] = ' / '.join(nodes[x]['label'] for x in sorted(tomerge))
                        for todelete in tomerge[1:len(tomerge)]:
                            for tfrom in nodes[todelete]['from']:
                                for iref,ref in reversed(list(enumerate(nodes[tfrom]['refs']))):
                                    if ref['to'] == todelete:
                                        #print '# deleting ref %s->%s (%i)' % (tfrom, todelete, iref)
                                        del nodes[tfrom]['refs'][iref]
                            for iref,tref in reversed(list(enumerate(nodes[todelete]['refs']))):
                                if tref['to'] not in nodes[merged]['to']:
                                    #print '# adding ref %s' % (tref['to'])
                                    nodes[merged]['refs'].append(tref)
                                    nodes[merged]['to'] |= {tref['to']}
                            #print '# deleting node %s' % todelete
                            del nodes[todelete]
                        return 1
    return 0

def split_states(nodes, prefix):
    splitStates0 = {}
    origSplitRefs = {}
    for id,node in nodes.items():
        thisrefs = {}
        for ref in node['refs']:
            to = ref['to']
            to0 = to
            if to in thisrefs:
                if to != thisrefs[to]:
                    ref['to']=thisrefs[to]
            elif to in splitStates or to[len(prefix):] in splitStates:
                if to in splitStates0:
                    if args.verbose:
                        print '# splitting %s' % to
                    to0 = to
                    to += str(splitStates0[to])
                    splitStates0[to0] += 1
                    ref['to'] = to
                    if len(nodes[to0]['refs']) == 0:
                        nodes[to] = nodes[to0].copy()
                        nodes[to]['pos']=len(nodes)
                        nodes[to]['split']=1
                    else:
                        nodes[to] = {'type':'?', 'pos':len(nodes), 'label':nodes[to0]['label'], 'flags':' style="dashed"', 'refs':[], 'split':1}
                        if to0 in origSplitRefs:
                            origSplitRefs[to0]['flags'] += ' color="purple"'
                            del origSplitRefs[to0]
                else:
                    splitStates0[to] = 0
                    origSplitRefs[to] = ref
                thisrefs[to0]=to
            
def post_process_flow(nodes, prefix):
    i = 0
    maxIter = 1000
    while i < maxIter and merge_nodes(nodes, prefix):
        i += 1
    if i == maxIter:
        print "# error: merge_nodes internal error : too many iterations"
    split_states(nodes, prefix)
            
def process_flow(id, flowXml):
    global out, nodes, extrefs, prefixN, clusterPrefix
    if args.verbose:
        print 'Processing flow %s' % id
    prefix = str(prefixN) + "."
    prefixN += 1
    nodes = {}
    print >>out, '  subgraph %s { label=%s; color="grey"; ' % (label(clusterPrefix + id), label(id))
    color = "red" if id == "start" else "orange"
    startStateLabel = 'start-state'
    startState = flowXml.get('start-state')
    if not startState:
        startStateLabel = ''
        for t in flowXml:
            if re.match(r'.*-state$', t.tag):
                startState = t.get('id')
                if args.verbose: print '# start state: %s' % startState
                break
    nodes[id]={'type':'flow', 'pos':len(nodes), 'label':id, 'flags':(' style="filled,bold" fillcolor="%s"' % color),
        'refs':[{'label':startStateLabel, 'to':prefix + startState, 'flags':''}]
    }
    for t in flowXml.findall('flow:action-state',ns):
        process_state(prefix, t, ' shape=box style=rounded')
    for t in flowXml.findall('flow:subflow-state',ns):
        process_state(prefix, t)
    for t in flowXml.findall('flow:view-state',ns):
        process_state(prefix, t,' shape=box style=filled fillcolor=lightgrey')
    for t in flowXml.findall('flow:decision-state',ns):
        process_state(prefix, t,' shape=diamond')
    for t in flowXml.findall('flow:end-state',ns):
        process_state(prefix, t, ' shape=doubleoctagon')
    post_process_flow(nodes, prefix)
    for id,node in sorted(nodes.items(), key=lambda t: t[1]['pos']):
        if 'external' not in node:
            print >>out, '    %s [label=%s%s]; ' % (label(id), label(node['label']), node['flags'])
        for ref in node['refs']:
            if ref['to'] and id != ref['to']:
                if 'external' not in ref:
                    print >>out, '    %s->%s [label=%s%s];' % (label(id), label(ref['to']), label(ref['label']), ref['flags'])
                else:
                    ref = ref.copy()
                    ref['from'] = id
                    ref['node'] = nodes[ref['to']]
                    extrefs.append(ref)
    print >>out, '  }'

def read_flow_registry(webflowXmlPaths):
    global out, extrefs, clusterPrefix, prefixN, dynCounter
    clusterPrefix = 'cluster'
    prefixN = 0
    dynCounter = 0
    extrefs = []
    for webflowXmlPath in glob.glob(webflowXmlPaths):
        if args.verbose: print "# processing %s" % webflowXmlPath
        webflowXml = ET.parse(webflowXmlPath).getroot()
        webflowXmlDir = os.path.dirname(os.path.abspath(webflowXmlPath))
        if webflowXml.tag == '{http://www.springframework.org/schema/webflow}flow':
            clusterPrefix = ''
            m = re.match(r'.*?(([^/\\\\]+[/\\\\]){'+str(args.flow_id_path_steps-1)+'}[^/\\\\]+)\.[^/\\\\.]+$', webflowXmlPath)
            if not m:
                m = re.match(r'.*?([^/\\]+)\.[^/\\.]+$', webflowXmlPath)
            process_flow(m.group(1).replace('\\','/'), webflowXml)
        for t in webflowXml.findall('.//flowcfg:flow-location', ns):
            path = t.get('path').replace('classpath:','')
            m = re.match(r'.*?(([^/\\\\]+[/\\\\]){'+str(args.flow_id_path_steps-1)+'}[^/\\\\]+)\.[^/\\\\.]+$', path)
            if not m:
                m = re.match(r'.*?([^/\\]+)\.[^/\\.]+$', path)
            id = t.get('id', m.group(1).replace('\\','/'))
            if os.path.exists(webflowXmlDir + '/' + path):
                webflowXmlPath = webflowXmlDir + '/' + path
            elif os.path.exists('.' + path):
                webflowXmlPath = '.' + path
            else:
                webflowXmlPath = path
            if id not in skipFlows:
                if args.split:
                    process_input(webflowXmlPath, id)
                    extrefs = []
                else:
                    flowXml = ET.parse(webflowXmlPath).getroot()
                    process_flow(id, flowXml)
        for ref in extrefs:
            print >>out, '  %s [label=%s%s]; ' % (label(ref['to']), label(ref['node']['label']), ref['node']['flags'])
            print >>out, '  %s->%s [label=%s%s];' % (label(ref['from']), label(ref['to']), label(ref['label']), ref['flags'])
        
def process_input(webflowXmlPath, output):
    global out
    if output:
        out = open(output, 'w')
    else:
        out = sys.stdout
    if output or not args.split:
        print >>out, 'strict digraph X {'
        print >>out, ' size="20,20"; overlap=false;concentrate=true;'#splines=false;'
        print >>out, ' compound=true;'
    read_flow_registry(webflowXmlPath)
    if output or not args.split:
        print >>out, '}'
    if output:
        out.close()
        out = sys.stdout
        if args.dot:
            subprocess.call(['dot', '-O', '-Tpdf', output])

process_input(args.input, args.output)
