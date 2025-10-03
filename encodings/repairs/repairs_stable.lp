%Generates the best candidate function for stable state observations.
%(In stable state mode we must ensure that, given the values of a compound's
%regulators, the compound is able to replicate its observed state).

#const compound = c.
#const max_node_number = n.

%*--Fixing regulators--*%
%fixed/2 tells us that regulator C has to be one of the compound's regulators
fixed_regulator(C) :- fixed(C,compound), compound(C).
fixed_regulator(C) :- fixed(C,compound,_), compound(C).

%Fixed/3. contains information regarding the sign of a fixed regulator
fixed_activator(C) :- fixed(C,compound,0), compound(C).
fixed_inhibitor(C) :- fixed(C,compound,1), compound(C).

%*--Assigning regulator signs--*%
%Fixed activators and inhibitors already have their regulation behavior defined
activator(C) :- fixed_activator(C).
inhibitor(C) :- fixed_inhibitor(C).

%A compound C can either be an inhibitor or an activator, but not both
1 {activator(C); inhibitor(C)} 1 :- compound(C), 
  not fixed_activator(C), not fixed_inhibitor(C).

%*--Creating nodes--*%
%Original node IDs must always be available 
%(so that we are able to make as little changes to the format of the original 
%nodes as possible, using optimizations #3). Note that we cannot simply 
%create all IDs using 1..max_node_number, since max_node_number may be smaller than
%the number of original nodes. This would cause us to potentially leave out 
%some original nodes when optimizing the format of our solution nodes
available_node_ID(1..TERM_NO) :- function(compound, TERM_NO).

%If we require more IDs than those that were originally available,
%create them
available_node_ID(1..max_node_number):- function(compound, TERM_NO), max_node_number > TERM_NO.

%Distribute compounds across available IDs
{node_regulator(N,C) : compound(C)} :- available_node_ID(N).

%Project the node IDs our solution is using into their own predicate
node_ID(N) :- node_regulator(N,_).

%If a node N1 has some regulating compound C which is not present in node N2,
%then N1 is distinct from N2 (used in integrity constraint #3)
distinct_nodes(N1,N2) :- node_regulator(N1,C), node_ID(N2), N1 < N2, not node_regulator(N2,C). 

%*--Assessing node behavior--*%
%If one of a node's variables has value 0 for experiment E, 
%then for that same experiment the node will also have value 0 (if that variable is an activator)
experiment_negative_node(E,N) :- node_regulator(N,C), curated_observation(E,C,0), activator(C).
%Variant for variables that are inhibitors
experiment_negative_node(E,N) :- node_regulator(N,C), curated_observation(E,C,1), inhibitor(C).

%Nodes that aren't negative in experiment E must be positive
experiment_positive_node(E,N) :- not experiment_negative_node(E,N), node_ID(N), curated_observation(E,_,_).


%Test
%1-We're only interested in generating nodes that can be used to explain the observations,
%which is not possible for a node to do if it is active when we expect it to be inactive
:- experiment_positive_node(E,N), curated_observation(E,compound,0).

%2-Every positive observation must be covered by some positive node
:- not experiment_positive_node(E,_), curated_observation(E,compound,1).

%3-Candidate nodes must be distinct
:- node_ID(N1), node_ID(N2), N1 < N2, not distinct_nodes(N1,N2).

%4-The BCF cannot be broken (nodes cannot contain other nodes)
:- N1_VARNO = #count{ C : node_regulator(N1,C) }, 
  COMMON_VARNO = #count{C : node_regulator(N1,C), node_regulator(N2,C)},   
  node_ID(N1), node_ID(N2), N1 != N2, COMMON_VARNO = N1_VARNO.

%5-Fixed regulators must be present in the final solution
:- fixed_regulator(C), not node_regulator(_,C).

%6-Used node IDs must be continuous
% In other words, if an available id higher than another availabe id is used than the lower id must also be used
% :- available_node_ID(N1), available_node_ID(N2), N1 < N2, node_ID(N2), not node_ID(N1).

%Display
regulator_activator(C) :- node_regulator(N,C), activator(C).
regulator_inhibitor(C) :- node_regulator(N,C), inhibitor(C).

#show node_ID/1.
#show regulator_activator/1.
#show regulator_inhibitor/1.
#show node_regulator/2.
