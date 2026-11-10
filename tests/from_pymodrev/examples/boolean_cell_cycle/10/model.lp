vertex(cyca).
vertex(rb).
vertex(cycb).
vertex(cdc20).
vertex(cdh1).
vertex(cycd).
vertex(cyce).
vertex(e2f).
vertex(p27).
vertex(ubch10).

edge(cycb, cdc20, 1).
edge(rb, cyca, 0).
edge(cyca, cyca, 1).
edge(cdc20, cyca, 0).
edge(cdh1, cyca, 0).
edge(ubch10, cyca, 0).
edge(cdc20, cycb, 0).
edge(cdh1, cycb, 0).
edge(cycd, cycd, 1).
edge(rb, cyce, 0).
edge(e2f, cyce, 1).
edge(rb, e2f, 0).
edge(cyca, e2f, 0).
edge(cycb, e2f, 1).
edge(p27, e2f, 1).
edge(cycd, rb, 1).
edge(cyce, rb, 0).
edge(cyca, rb, 0).
edge(cycb, rb, 0).
edge(p27, rb, 1).
edge(cdc20, ubch10, 1).
edge(ubch10, ubch10, 1).
edge(cycb, ubch10, 1).
edge(cyca, ubch10, 0).
edge(cdh1, ubch10, 0).
edge(cyca, cdh1, 0).
edge(cycb, cdh1, 0).
edge(p27, cdh1, 1).
edge(cdc20, cdh1, 1).
edge(cycd, p27, 0).
edge(cyce, p27, 1).
edge(cyca, p27, 0).
edge(cycb, p27, 0).
edge(p27, p27, 1).
edge(cycd, cycb, 0).
functionOr(cdc20, 1).
functionAnd(cdc20, 1, cycb).
functionOr(cdh1, 1..3).
functionAnd(cdh1, 1, cyca).
functionAnd(cdh1, 1, cycb).
functionAnd(cdh1, 2, cycb).
functionAnd(cdh1, 2, p27).
functionAnd(cdh1, 3, cdc20).
functionOr(cyca, 1..2).
functionAnd(cyca, 1, cdc20).
functionAnd(cyca, 1, cdh1).
functionAnd(cyca, 1, cyca).
functionAnd(cyca, 1, ubch10).
functionAnd(cyca, 2, cdc20).
functionAnd(cyca, 2, cdh1).
functionAnd(cyca, 2, rb).
functionAnd(cyca, 2, ubch10).
functionOr(cycb, 1..2).
functionAnd(cycb, 1, cdh1).
functionAnd(cycb, 1, cycd).
functionAnd(cycb, 2, cdc20).
functionAnd(cycb, 2, cycd).
functionOr(cycd, 1).
functionAnd(cycd, 1, cycd).
functionOr(cyce, 1..2).
functionAnd(cyce, 1, rb).
functionAnd(cyce, 2, e2f).
functionOr(e2f, 1).
functionAnd(e2f, 1, rb).
functionAnd(e2f, 1, cyca).
functionAnd(e2f, 1, cycb).
functionAnd(e2f, 1, p27).
functionOr(p27, 1..3).
functionAnd(p27, 1, cycd).
functionAnd(p27, 1, cyce).
functionAnd(p27, 1, cyca).
functionAnd(p27, 1, cycb).
functionAnd(p27, 2, cycd).
functionAnd(p27, 2, cyca).
functionAnd(p27, 2, p27).
functionAnd(p27, 2, cycb).
functionAnd(p27, 3, cycd).
functionAnd(p27, 3, cyce).
functionAnd(p27, 3, p27).
functionAnd(p27, 3, cycb).
functionOr(rb, 1..2).
functionAnd(rb, 1, cycd).
functionAnd(rb, 1, cyce).
functionAnd(rb, 1, cyca).
functionAnd(rb, 1, cycb).
functionAnd(rb, 2, cycd).
functionAnd(rb, 2, p27).
functionAnd(rb, 2, cycb).
functionOr(ubch10, 1..4).
functionAnd(ubch10, 1, cdc20).
functionAnd(ubch10, 1, ubch10).
functionAnd(ubch10, 2, cycb).
functionAnd(ubch10, 2, ubch10).
functionAnd(ubch10, 3, cyca).
functionAnd(ubch10, 3, ubch10).
functionAnd(ubch10, 4, cdh1).
