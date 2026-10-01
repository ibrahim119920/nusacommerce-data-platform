-- Fixtures emulate an upstream history feed and transaction-time prices.
INSERT INTO landing.raw_customer_history VALUES
 ('cust-001','Jakarta','silver','2026-01-01T00:00:00+07:00','2026-09-27T08:15:00+07:00'),
 ('cust-001','Bandung','gold','2026-09-27T08:15:00+07:00',NULL),
 ('cust-002','Surabaya','silver','2026-01-01T00:00:00+07:00',NULL),
 ('cust-003','Jakarta','regular','2026-01-01T00:00:00+07:00',NULL),
 ('cust-004','Medan','gold','2026-01-01T00:00:00+07:00',NULL),
 ('cust-005','Bandung','regular','2026-01-01T00:00:00+07:00',NULL)
 ON CONFLICT DO NOTHING;
INSERT INTO landing.raw_products VALUES
 ('prod-1','Keyboard','electronics',150000),
 ('prod-2','Headphones','electronics',300000),
 ('prod-3','Bag','accessories',100000) ON CONFLICT DO NOTHING;
INSERT INTO landing.raw_order_items VALUES
 ('ord-1001',1,'prod-1',1,125000),('ord-1002',1,'prod-2',1,250000),
 ('ord-1003',1,'prod-3',1,89000),('ord-1004',1,'prod-1',1,175000),
 ('ord-1005',1,'prod-2',1,310000),('ord-1006',1,'prod-3',1,0),
 ('ord-1007',1,'prod-2',1,499000),('ord-1008',1,'prod-3',1,72000)
 ON CONFLICT DO NOTHING;
INSERT INTO landing.raw_refunds VALUES
 ('refund-1','ord-1005',25000,'IDR','2026-09-29T11:00:00+07:00') ON CONFLICT DO NOTHING;
