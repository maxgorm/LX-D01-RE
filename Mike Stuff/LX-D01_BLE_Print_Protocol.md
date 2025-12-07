# LX-D01 BLE Print Protocol (from Full_BT_Logs.txt)

Assumptions: ATT MTU 23 (20-byte GATT payloads). All multi-byte fields little-endian.

## Session Timeline (Dec 04 00:50:08–00:50:14)
- 00:50:08.950 connect to `LX-D01` (link handle later 0x005B).
- 00:50:09.905 notify `0x0006`: `5A02 5B00 0000 0003 0F40 0040` (initial status/caps).
- 00:50:10.520 host write `0x0003`: `5A04 003A 0001 0000 0000 0000` (start job: 0x3A blocks, job/copies=1).
- 00:50:10.520–11.225 host streams 58 data blocks (`55` frames) indexes 0x0000–0x0039.
- 00:50:10.567 notify: `5A07 1400 0000 0000 0000 0000` (ready/progress marker; 0x0014=20).
- 00:50:10.582 notify: `5A04 003A 0001 0000 0000 0000` (job accepted echo).
- 00:50:12.980 notify: `5A06 003A 0100 0000 0000 0000` (job complete).
- 00:50:12.981 host ACK write: `5A04 003A 0100 0000 0000 0000`.
- 00:50:13.026 notify repeats `5A04 003A 0100 0000 0000 0000` (completion replay).
- 00:50:14.533 link lost.

## Handles and Roles
- Write Without Response characteristic: handle `0x0003` (host → device).
- Notify characteristic: handle `0x0006` (device → host). CCC handle not present in log; must be discovered.

## Control Frames (`5A` opcodes; words are 16-bit)
- `5A02 5B00 0000 0003 0F40 0040` (notify)
  - op=0x02
  - w1=`0x005B` (connection handle reference?)
  - w2=`0x0000` (status?)
  - w3=`0x0003` (capability/version?)
  - w4=`0x400F` (caps/width/buffer?)
  - w5=`0x4000` (caps/width/buffer?)
- `5A04 003A 0001 0000 0000 0000` (host→dev start, dev→host echo)
  - op=0x04
  - w1=`block_count=0x003A` (58 blocks follow)
  - w2=`job_id_or_copies=0x0001`
  - w3=`0x0000` (status)
  - w4=`0x0000`
  - w5=`0x0000`
- `5A07 1400 0000 0000 0000 0000` (notify mid-job)
  - op=0x07
  - w1=`0x0014` (20) ready/remaining marker
  - w2–w5=`0x0000`
- `5A06 003A 0100 0000 0000 0000` (notify completion)
  - op=0x06
  - w1=`block_count=0x003A`
  - w2=`0x0100` (result/ack token)
  - w3–w5=`0x0000`
  - Host answers with `5A04 …0100…` (ACK), printer repeats until seen.

## Data Frames (`55` prefix; 20-byte writes)
- Format per packet: `55 00 <idx_L> <idx_H> <16-byte payload>`.
- Index increments sequentially from 0x0000 to 0x0039 (58 blocks = `block_count`).
- Payload appears raster/bitmap; early blocks dense (`FF/F0`), tail blocks (≥0x2D) all zeros (trailing blank space).
- Transport: Write Without Response on `0x0003`; controller flow control shows ~2 outstanding writes (HCI completed-packets mostly 0x0002).

## End-to-End Print Workflow (driver guidance)
1) Connect, discover service/characteristics; enable notifications on handle `0x0006` (find CCC handle via discovery).
2) Wait/accept initial status `5A02 …` (optional but useful for caps).
3) Start job: write `5A04 <block_count> <job_id/copies> 0000 0000 0000` to `0x0003`.
4) Stream data blocks: for i=0..block_count-1 send 20-byte write `55 00 <i_le> <payload16>` to `0x0003`. Keep ≤2 in flight unless testing proves higher window.
5) Observe notifies on `0x0006`: `5A04` echo (job accepted), possible `5A07` (ready/progress), then `5A06` (completion).
6) On `5A06 …`, ACK by writing `5A04 <block_count> 0100 0000 0000 0000` to `0x0003`. Expect device to repeat completion until ACKed.
7) Close or disconnect when done.

### Sequence (text diagram, MTU 23)
```
Phone                         Printer
----------------------------------------------
(notify enable on 0x0006) ->
<- 5A02 status
5A04 start (blocks=N, id=1) ->
55 00 0000 +16B payload     ->
55 00 0001 +16B payload     ->   (continues sequentially to 0039)
...                         ->
<- 5A07 (ready/progress)
<- 5A04 echo (job accepted)
<- 5A06 complete (blocks=N)
5A04 ACK (blocks=N, token)  ->
<- 5A04 repeat (until ACK seen)
```

### Host pseudocode (20-byte payload, 16-byte data slices)
```
mtu = 23
payload_len = 16  # 20 - 4-byte header

discover handles:
  write_char = 0x0003
  notify_char = 0x0006
  ccc = discover_ccc_for(notify_char)

enable_notify(ccc)

blocks = len(image_bytes) / payload_len  # must be integer; pad with 0x00 to fit
send(write_char, sa(0x5A04, blocks, job_id=1, 0, 0, 0))  # Write Command

for i in range(blocks):
  chunk = image_bytes[i*payload_len:(i+1)*payload_len]
  pkt = b"\x55\x00" + le16(i) + chunk
  send_wwr(write_char, pkt)  # pace to ~2 outstanding

wait_for_notify(op=0x5A06, block_count=blocks)

# ACK completion
send(write_char, sa(0x5A04, blocks, 0x0100, 0, 0, 0))

# drain any repeated 5A04 echoes, then close
```

## Open Questions / Validation
- Determine CCC descriptor handle for `0x0006` to enable notifications.
- Clarify meanings of `5A02` fields (`0x0003`, `0x400F`, `0x4000`)—likely width/buffer/capability values.
- Check if outstanding write window can exceed 2 without stalls.
- Confirm semantics of `w2` in `5A04/06` (job id vs copies vs ack token).
